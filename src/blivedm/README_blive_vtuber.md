以下是双语版本的说明文档：

---

# blivedm_broadcast_dm

Integrate the `blivedm` library into `open-llm-vtuber` to enable LLM to interact with danmaku (live stream comments): [blivedm](https://github.com/xfgryujk/blivedm)

将 `blivedm` 库接入到 `open-llm-vtuber` 中，以实现 LLM 与弹幕进行对话的功能：[blivedm](https://github.com/xfgryujk/blivedm)

---

## Usage Instructions / 使用说明

1. Run the server:
   ```bash
   uv run run_server_dm.py
   ```

   运行服务器：
   ```bash
   uv run run_server_dm.py
   ```

2. In `broadcast_dm.py`, fill in the room ID and the `SESSDATA` field of the logged-in account's cookie. It can run without these, but the usernames of the danmaku senders will not be visible.

   在 `broadcast_dm.py` 中填入房间号和已登录账号的 `SESSDATA` 字段的值。不填也能运行，只是无法查看发送弹幕的用户名。

3. Run `broadcast_dm.py`:
   ```bash
   python broadcast_dm.py
   ```

   运行 `broadcast_dm.py`：
   ```bash
   python broadcast_dm.py
   ```

4. If you need to integrate danmaku from other platforms, you can refer to the `broadcast_client()` method in `broadcast_dm.py`, or use `test_broadcast.py` for testing.

   若需要接入其他平台的弹幕，可以参考 `broadcast_dm.py` 中的 `broadcast_client()` 方法，或者使用 `test_broadcast.py` 进行测试。

---

### Known Bugs / 已知问题

1. The frontend cannot display messages sent by the `broadcast_client()` method correctly, but the history records them properly.

   前端无法正常显示 `broadcast_client()` 方法发送的消息，但是历史记录却能正常记录。

2. A legacy bug in `gptsovits`: When the LLM outputs text containing "哈哈哈", it causes `gptsovits` to return a reference audio (this bug occurs when the text is in Chinese and the audio is in Japanese; it is unclear if it happens with other languages or the same language).

   `gptsovits` 历史遗留问题：当 LLM 输出的文本中带有 "哈哈哈" 时，会导致 `gptsovits` 返回的音频为参考音频（文本为中文，音频为日语的情况下遇到此问题；相同语言或其他语言的情况尚不清楚）。

---

This bilingual documentation provides clear instructions and highlights known issues for users. Let me know if you need further assistance!