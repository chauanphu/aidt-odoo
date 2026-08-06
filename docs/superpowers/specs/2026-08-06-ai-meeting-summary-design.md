# Design Spec: Odoo AI Meeting Summary (JSON & Data Models)

## 1. Overview
The current implementation of the `aidt_meeting_minutes` addon returns unstructured text summaries. According to the requirements in `odoo_ai_meeting_summary_usecase_pipeline.md`, the AI output must follow a strict JSON schema that breaks the summary into actionable items, decisions, and overview information. This specification outlines the changes required to upgrade the meeting recording data models and prompt logic to generate, validate, and store structured JSON data.

## 2. Architecture & Data Models

Instead of creating an entirely new 1:1 summary model, we will extend the existing `aidt.meeting.recording` model to house the general summary data and add related models for list-based entities.

### 2.1. `aidt.meeting.recording` Extensions
Add the following fields to store the high-level summary results:
- `title` (Char): Meeting title.
- `overview` (Text): High-level summary of the meeting.
- `meeting_minutes` (Text): Complete, structured meeting minutes.
- `key_points` (Text/JSON): Stored as JSON string or plain text list.
- `risks` (Text/JSON): Stored as JSON string or plain text list.
- `action_item_ids` (One2many): Linked to `aidt.meeting.action.item`.
- `decision_ids` (One2many): Linked to `aidt.meeting.decision`.

### 2.2. New Model: `aidt.meeting.action.item`
- `recording_id` (Many2one): Link back to the meeting recording.
- `task` (Text): The action to be performed.
- `owner` (Char): The person assigned.
- `deadline` (Char/Date): Extracted deadline.
- `priority` (Selection): high, medium, low.
- `timestamp` (Char): Time reference from transcript.

### 2.3. New Model: `aidt.meeting.decision`
- `recording_id` (Many2one): Link back to the meeting recording.
- `content` (Text): The decision made.
- `timestamp` (Char): Time reference from transcript.

## 3. LLM Integration (`summary_client.py`)

### 3.1. Map-Reduce Strategy
To prevent malformed JSON midway, the map-reduce strategy remains text-based for partial chunks. Only the **Final Summarization** step will be instructed to output JSON.

### 3.2. Prompts
- **Partial Prompt (`SYSTEM_PROMPT`)**: Remains a standard text summarization prompt.
- **Final Prompt (`FINAL_JSON_PROMPT`)**: Added to instruct the LLM to synthesize the partial summaries and output strictly in the exact required JSON schema (matching the requirements doc section 10).

### 3.3. JSON Validation & Fallback
- `_summarize` will extract the JSON payload (stripping any ````json ... ```` markdown blocks).
- Attempt `json.loads`.
- If parsing fails, retry calling the LLM up to 2 times.
- If all retries fail, raise `SummaryError` (triggering the existing fallback behavior where it logs the error to the database).
- Return a parsed Python dictionary instead of a raw string.

## 4. Integration & UI (`meeting_recording.py` & Views)

### 4.1. Processing the Output
- Modify `_run_summary()`:
  - Call `_summarize()` and expect a dictionary.
  - Update text fields (`title`, `overview`, `meeting_minutes`).
  - Delete (`unlink`) any existing `action_item_ids` and `decision_ids` attached to the recording to allow safe "Re-generation" of summaries.
  - Iterate through `action_items` and `decisions` in the dict and create records in the respective models.

### 4.2. Chatter Output
- Post a well-formatted chatter message containing the `Title`, `Overview`, and a brief count of generated decisions and action items, replacing the current behavior of dumping the entire summary text.

### 4.3. UI (Views)
- Refactor the Form View of `aidt.meeting.recording` to use `<notebook>`:
  - **Tab 1: Overview & Minutes**: Displays `overview`, `key_points`, `risks`, and `meeting_minutes`.
  - **Tab 2: Action Items**: Embedded tree view of `action_item_ids`.
  - **Tab 3: Decisions**: Embedded tree view of `decision_ids`.
  - **Tab 4: Transcript**: Displays the raw transcript text.

## 5. Security & Access Rights
- Add standard `ir.model.access.csv` rules for `aidt.meeting.action.item` and `aidt.meeting.decision`, mirroring the read/write permissions of `aidt.meeting.recording`.
