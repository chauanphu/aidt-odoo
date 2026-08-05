# syntax=docker/dockerfile:1
# =============================================================================
# aidt-odoo — production image built from this source tree
# Stages:
#   builder — compiles Python dependencies into a virtualenv
#   runtime — slim production image (default target)
#   dev     — runtime + developer tooling; source is bind-mounted at run time
# =============================================================================

# ----------------------------------------------------------------------------
# Stage 1: build Python dependencies
# ----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libjpeg-dev \
        libldap2-dev \
        libpq-dev \
        libsasl2-dev \
        libssl-dev \
        libxml2-dev \
        libxslt1-dev \
        pkg-config \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip wheel \
    && pip install -r /tmp/requirements.txt

# Phụ thuộc của CUSTOM ADDON, cố ý để riêng khỏi requirements.txt —
# requirements.txt là file thượng nguồn của Odoo, trộn phụ thuộc của ta vào
# đó sẽ làm mọi lần nâng cấp Odoo thành một cuộc merge thủ công.
#
# `av` + `numpy`: aidt_meeting_minutes/models/audio_prep.py — giải mã MP3,
# lọc tiếng nói và chuẩn hoá audio trước khi gọi ASR. Import ở TẦNG MODULE
# (cố ý, xem docstring của audio_prep): thiếu gói thì cài đặt addon phải nổ
# to ngay lúc cài, chứ không được âm thầm bỏ qua mọi mẩu audio và xoá trắng
# biên bản của mọi cuộc họp.
#
# PHẢI CÓ Ở ĐÂY, KHÔNG ĐƯỢC chỉ `pip install` trong container đang chạy.
# Ngày 05/08/2026 phát hiện cả ba gói này chỉ tồn tại ở lớp ghi của
# `aidt-odoo-dev-odoo-1` (ai đó cài tay); ảnh dựng lại từ Dockerfile này
# KHÔNG có chúng. `docker run --rm --entrypoint python3 aidt-odoo-dev-odoo:latest
# -c "import av"` -> ModuleNotFoundError. Tức là một lần rebuild bất kỳ sẽ
# làm module không cài được nữa, và không có gì trong repo báo trước điều đó.
#
# `av` không cần ffmpeg của hệ thống: wheel manylinux của PyAV đóng gói sẵn
# thư viện FFmpeg bên trong. Ghim version đúng bằng docker/asr.Dockerfile để
# hai container không lệch bộ giải mã audio.
RUN pip install --no-cache-dir av==18.0.0 numpy==2.5.1

# ----------------------------------------------------------------------------
# Stage 2: production runtime
# ----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Runtime libraries, fonts, tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-dejavu-core \
        fonts-liberation \
        fonts-noto \
        fonts-noto-cjk \
        gettext-base \
        libjpeg62-turbo \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        libldap-2.5-0 \
        libpq5 \
        libsasl2-2 \
        libxml2 \
        libxslt1.1 \
        nodejs \
        npm \
        poppler-utils \
        postgresql-client \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

# wkhtmltopdf (patched Qt build — required for PDF report headers/footers)
RUN curl -fsSL -o /tmp/wkhtmltox.deb \
        "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.bookworm_$(dpkg --print-architecture).deb" \
    && apt-get update \
    && apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb \
    && rm -rf /tmp/wkhtmltox.deb /var/lib/apt/lists/*

# rtlcss for right-to-left language asset generation
RUN npm install -g rtlcss

# Non-root user; fixed uid keeps volume ownership stable across rebuilds
RUN groupadd -g 101 odoo \
    && useradd -r -u 101 -g odoo -d /var/lib/odoo -s /usr/sbin/nologin odoo \
    && mkdir -p /var/lib/odoo /etc/odoo /opt/odoo \
    && chown -R odoo:odoo /var/lib/odoo /etc/odoo /opt/odoo

COPY --from=builder /opt/venv /opt/venv

# Odoo source (production bakes the source into the image)
COPY --chown=odoo:odoo . /opt/odoo

COPY --chown=odoo:odoo docker/odoo.conf /etc/odoo/odoo.conf.template
COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

USER odoo
WORKDIR /opt/odoo

VOLUME ["/var/lib/odoo"]
EXPOSE 8069 8072

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8069/web/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]

# ----------------------------------------------------------------------------
# Stage 3: development (bind-mount the source over /opt/odoo)
# ----------------------------------------------------------------------------
FROM runtime AS dev

USER root
# chromium: required by `HttpCase.browser_js`, which is how the OWL/hoot suites
# under `custom-addons/*/static/tests/*.test.js` actually execute. Without it
# `browser_js` raises unittest.SkipTest — it SKIPS rather than FAILS, so a
# missing browser looks exactly like a green run. That is not hypothetical:
# aidt_meeting_minutes' three hoot suites silently never ran for eleven tasks
# for precisely this reason, and running them the first time immediately found
# two real defects. Installing it here is what keeps that from recurring.
RUN apt-get update && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*

# watchdog: enables --dev=reload auto-restart; debugpy: remote debugging (VS Code attach);
# pytest: test runner for pure-Python libraries under custom-addons (e.g. aidt_search_engine);
# websocket-client: the OTHER half of browser_js — without it the test skips
# before Chrome is ever launched (odoo/tests/common.py, "websocket-client
# module is not installed").
#
# soundfile: CHỈ dùng trong tests/test_audio_prep.py để đọc ngược tệp WAV do
# `_encode_wav` sinh ra bằng một bộ giải mã ĐỘC LẬP với PyAV — tự đọc lại
# bằng chính thư viện vừa ghi ra thì không chứng minh được header RIFF đúng.
# Để ở stage `dev` chứ không phải builder vì production không chạy test.
RUN pip install --no-cache-dir debugpy watchdog ipython pytest websocket-client \
    soundfile==0.14.0

# entrypoint.sh installs/upgrades these on aidt_demo on every container start
# (see docker/entrypoint.sh), so a rebuild always registers custom-addon code
# changes without a manual `-u`/`-i`. Unset in the `runtime` stage above, so
# production never auto-migrates a live database on restart. Add new custom
# modules to this list as they're created.
ENV ODOO_UPDATE_DB=aidt_demo \
    ODOO_UPDATE_MODULES=aidt_base,aidt_calendar,aidt_calendar_demo,aidt_dashboard_builder,aidt_dashboard_demo,aidt_dms,aidt_dms_demo,aidt_format,aidt_meeting_minutes,aidt_org,aidt_org_demo,aidt_search,aidt_task,aidt_task_demo,aidt_vanban_demo,aidt_vanban_den,aidt_vanban_di

USER odoo
