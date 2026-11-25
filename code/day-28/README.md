# Hands-On Lab: Day 28 - Terminal Multiplexing Orchestrator (`tmux_session_orchestrator.py`)

## 1. What Are We Building & Why Does It Matter?
Terminal multiplexers (`tmux`) run a background server daemon that holds open pseudo-terminals (`/dev/pts/N`).
Even if your laptop battery dies or Wi-Fi drops, the commands running inside tmux continue executing uninterrupted.
When you reconnect, `tmux attach` restores your exact screen layout and running programs.

In this lab, we build `tmux_session_orchestrator.py` to model the hierarchical relationship between the tmux Server, Sessions, Windows, and Panes.

---

## 2. Python Concepts for Beginners
1. **Object Composition**:
   - A `TmuxServer` contains a dictionary of `Session`s.
   - Each `Session` contains a list of `Window`s.
   - Each `Window` contains a list of `Pane`s.
2. **List Aggregations (`sum(...)`)**:
   - `sum(len(w.panes) for w in windows)` computes total panes across all windows.

---

## 3. Step-by-Step Code Walkthrough

```python
# Create a session and split into multiple panes:
app_win = server.new_session("prod_stack", "app")
app_win.panes[0].send_keys("python api_server.py")
metrics_pane = app_win.split_pane("htop")
```
- Models the exact commands executed when running `tmux new-session -d` and `tmux split-window`.

---

## 4. How to Run the Script

```bash
cd code/day-28
python tmux_session_orchestrator.py
```

### Expected Output
```
====================================================
TMUX TERMINAL MULTIPLEXER SESSION ORCHESTRATOR
====================================================
Active Sessions in Background Tmux Daemon:
  Session 'prod_stack': 1 Window(s), 2 Active Pane(s)

Pane 0 Output Buffer:
  |-- EXEC: python api_server.py

Pane 1 Output Buffer:
  |-- EXEC: start_monitoring

[SUCCESS] Headless terminal multiplexing verified operational!
```
---
---

## 5. Common Python Errors & Troubleshooting
1. **`KeyError: 'session_name'`**:
   - Attempting to access an uninitialized session raises `KeyError`. Use `.get()` or check `if session_name in sessions:` first.
2. **Window / Pane Index Off-by-One**:
   - By default, tmux numbers windows starting at `0`, but many users configure `base-index 1`. Be consistent with 0-indexed or 1-indexed numbering in your simulator.
3. **Deadlock on Synchronous IPC**:
   - When tmux orchestrates commands across multiple panes, waiting synchronously for output can hang if a command waits for interactive user input.

---

## 6. Beginner Exercises & Challenges
1. **Window vs Pane Modeling**:
   - In tmux, a Session contains multiple Windows (virtual desktops), and each Window can be split into multiple Panes. Extend `tmux_session_orchestrator.py` to model this two-tier hierarchy.
2. **Automate a Development Layout**:
   - Write a script that configures an IDE layout: Pane 0 (editor, 70% width), Pane 1 (build runner, 30% top), Pane 2 (server logs, 30% bottom).
3. **Session Detach and Reattach**:
   - Simulate a client detaching from a session (`Ctrl+B, d`) and a second client reattaching (`tmux attach -t dev`), verifying that background processes never stopped.
