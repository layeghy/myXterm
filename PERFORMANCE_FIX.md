# Performance Optimization for myXterm Terminal

## Problem
Running commands that produce large output (like `ps aux`, `find . -mindepth 2`, etc.) made the terminal extremely slow and even caused it to freeze, while other tools like MobaXterm handled these commands smoothly.

## Root Cause
The terminal was performing a **complete redraw on every data chunk received**:

1. **Backend** (`ssh/backend.py`): Read 1024 bytes at a time from SSH
2. **SSHReaderThread** (`ui/terminal.py`): Emitted each chunk as a separate signal
3. **Terminal Widget**: Each signal triggered `on_data_received()` → `refresh_display()` → `setPlainText()`

For commands with large output:
- Hundreds of small data chunks per second
- Each chunk triggered a full widget redraw
- `setPlainText()` is expensive - rebuilds the entire QPlainTextEdit
- Result: CPU maxed out trying to redraw faster than data arrives

## Solution Implemented

### 1. **Batched Display Updates** (Primary Fix)
- Added a `QTimer` that fires at ~60 FPS (every 16ms)
- `on_data_received()` now only marks `pending_updates = True` and starts the timer
- The timer callback (`_do_refresh()`) performs the actual display update
- Multiple data chunks received within 16ms are batched into a single redraw

**Impact**: Reduced redraws from hundreds per second to max 60 per second

### 2. **Larger Read Buffer**
- Increased SSH read buffer from 1024 to 8192 bytes
- Reduces the number of read operations and signal emissions
- Fewer context switches between reader thread and GUI thread

**Impact**: Up to 8x fewer signal emissions for continuous output

### 3. **Proper Cleanup**
- Added timer cleanup in `closeEvent()` to prevent timer events after widget destruction

## Code Changes

### `ui/terminal.py`:
1. **`__init__` method**: 
   - Reorganized initialization order (screen setup before reader thread)
   - Added refresh timer configuration
   - Added `pending_updates` flag

2. **`on_data_received` method**:
   - Changed from immediate `refresh_display()` to scheduled update
   - Starts timer only if not already running

3. **New `_do_refresh` method**:
   - Timer callback that checks `pending_updates` flag
   - Performs the actual `refresh_display()` call

4. **`closeEvent` method**:
   - Added timer cleanup

### `ssh/backend.py`:
1. **`read_output` method**:
   - Increased buffer size from 1024 to 8192 bytes

## Performance Characteristics

### Before:
- **Small output** (few lines): Acceptable
- **Large output** (hundreds of lines): System freezes/becomes unresponsive
- **Continous output**: CPU at 100%, GUI blocked

### After:
- **Small output**: Identical performance
- **Large output**: Smooth rendering, no freezes
- **Continuous output**: CPU usage reasonable, GUI remains responsive
- **Display lag**: Maximum 16ms (imperceptible to users)

## Technical Details

The 60 FPS refresh rate (16ms interval) strikes a balance:
- Fast enough that updates appear instantaneous to users
- Slow enough to batch multiple data chunks
- Matches typical monitor refresh rates
- Prevents overwhelming the Qt event loop

For commands that output data faster than 60 FPS:
- Data continues to feed into the pyte terminal emulator
- Only the display update is throttled
- No data is lost - it all accumulates in the screen buffer
- When output stops, one final update renders everything

## Compatibility

- Works with both SSH sessions and local sessions
- No changes to protocol handling or terminal emulation
- Maintains all existing features (scrollback, selection, etc.)
- No breaking changes to the API

## Testing Recommendations

Test with these commands to verify performance:
```bash
# Large file listing
find / -type f 2>/dev/null

# Process listing
ps aux

# Recursive directory listing  
ls -laR /

# Large log file
cat /var/log/syslog

# Continuous output
tail -f /var/log/syslog
```

All should now render smoothly without freezing the UI.
