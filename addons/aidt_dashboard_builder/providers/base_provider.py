from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """Lớp cơ sở trừu tượng cho tất cả Data Providers."""

    @abstractmethod
    def fetch_data(self, env, widget, filter_values=None):
        """Hàm lấy dữ liệu bắt buộc triển khai ở Provider con."""
        pass
