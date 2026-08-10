"""Shared bridge: dataset row -> Qwen chat messages.

Used by BOTH the training pipeline and the live AI service, so the exact
same system prompt and message structure is guaranteed at train time and
inference time. A mismatch here would silently degrade quality -- see
Qwen_Setup_and_Dataset_Creation.md, Step 13.
"""

SYSTEM_PROMPT = (
    "أنت مساعد متخصص في تحليل بيانات الاستشعار عن بعد. "
    "اعتمد فقط على البيانات المقدمة لك."
)


def row_to_messages(row: dict) -> list[dict]:
    """Convert one dataset row ({instruction, input, output, ...}) into
    Qwen's chat message format."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{row['instruction']}\n{row['input']}"},
        {"role": "assistant", "content": row["output"]},
    ]
