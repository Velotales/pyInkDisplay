# Power-Aware Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the main run loop so battery mode is a strict one-shot cycle (fetch → display → set alarm → publish → shut down now) while USB mode keeps the existing continuous loop.

**Architecture:** Extract `runBatteryMode()` from `pyInkPictureFrame()`. Move the power check earlier so alarm setting and battery publish happen inside each branch rather than before the branch. Change `shutdown +1` to `shutdown now`.

**Tech Stack:** Python 3.8+, `subprocess`, `unittest.mock`

---

### Task 1: Extract `runBatteryMode()` with immediate shutdown

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Test: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_py_ink_picture_frame.py`:

```python
from unittest.mock import MagicMock, call, patch

from pyinkdisplay.pyInkPictureFrame import runBatteryMode


def test_runBatteryMode_sets_alarm_and_shuts_down():
    """Battery mode sets alarm, publishes battery, and shuts down."""
    alarm = MagicMock()
    alarm.get_battery_level.return_value = 75

    with patch("pyinkdisplay.pyInkPictureFrame.subprocess.run") as mock_run, \
         patch("pyinkdisplay.pyInkPictureFrame.publishBatteryLevel") as mock_pub:
        runBatteryMode(alarm, alarmMinutes=20, mqttConfig={"host": "localhost"}, noShutdown=False)

    alarm.setAlarm.assert_called_once_with(secondsInFuture=1200)
    mock_pub.assert_called_once_with(alarm, {"host": "localhost"})
    mock_run.assert_called_once_with(["sudo", "shutdown", "now"], check=True)


def test_runBatteryMode_no_shutdown_when_flag_set():
    """Battery mode skips shutdown when noShutdown=True."""
    alarm = MagicMock()

    with patch("pyinkdisplay.pyInkPictureFrame.subprocess.run") as mock_run, \
         patch("pyinkdisplay.pyInkPictureFrame.publishBatteryLevel"):
        runBatteryMode(alarm, alarmMinutes=20, mqttConfig=None, noShutdown=True)

    mock_run.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_py_ink_picture_frame.py::test_runBatteryMode_sets_alarm_and_shuts_down tests/test_py_ink_picture_frame.py::test_runBatteryMode_no_shutdown_when_flag_set -v
```

Expected: FAIL with `ImportError: cannot import name 'runBatteryMode'`

- [ ] **Step 3: Implement `runBatteryMode()` in `pyinkdisplay/pyInkPictureFrame.py`**

Add this function after the existing `publishBatteryLevel` function:

```python
def runBatteryMode(alarmManager, alarmMinutes, mqttConfig, noShutdown):
    """
    One-shot battery cycle: set alarm, publish battery level, shut down immediately.

    Args:
        alarmManager: PiSugarAlarm instance.
        alarmMinutes (int): Minutes until next RTC wake alarm.
        mqttConfig (dict or None): MQTT configuration dict.
        noShutdown (bool): If True, skip the shutdown command (for testing).
    """
    secondsInFuture = alarmMinutes * 60
    logging.info("Battery mode: setting alarm for %d minutes (%d seconds).", alarmMinutes, secondsInFuture)
    alarmManager.setAlarm(secondsInFuture=secondsInFuture)
    publishBatteryLevel(alarmManager, mqttConfig)

    if not noShutdown:
        logging.info("Battery mode complete. Shutting down now.")
        try:
            subprocess.run(["sudo", "shutdown", "now"], check=True)
        except Exception as e:
            logging.error("Error during shutdown: %s", e)
    else:
        logging.info("Skipping shutdown due to --noShutdown flag.")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_py_ink_picture_frame.py::test_runBatteryMode_sets_alarm_and_shuts_down tests/test_py_ink_picture_frame.py::test_runBatteryMode_no_shutdown_when_flag_set -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "feat: add runBatteryMode() with immediate shutdown"
```

---

### Task 2: Refactor `pyInkPictureFrame()` to use `runBatteryMode()`

**Files:**
- Modify: `pyinkdisplay/pyInkPictureFrame.py`
- Test: `tests/test_py_ink_picture_frame.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_py_ink_picture_frame.py`:

```python
from pyinkdisplay.pyInkPictureFrame import pyInkPictureFrame


def test_pyInkPictureFrame_calls_runBatteryMode_when_not_powered():
    """Main function calls runBatteryMode when PiSugar is not on mains power."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setupLogging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay") as mock_display, \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode") as mock_battery, \
         patch("pyinkdisplay.pyInkPictureFrame.continuousEpdUpdateLoop") as mock_usb:

        mock_args.return_value.config = None
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = False
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_battery.assert_called_once()
    mock_usb.assert_not_called()


def test_pyInkPictureFrame_calls_continuousLoop_when_powered():
    """Main function enters continuous loop when PiSugar is on mains power."""
    with patch("pyinkdisplay.pyInkPictureFrame.parseArguments") as mock_args, \
         patch("pyinkdisplay.pyInkPictureFrame.loadConfig", return_value={}), \
         patch("pyinkdisplay.pyInkPictureFrame.mergeArgsAndConfig", return_value={
             "epd": "waveshare_epd.epd7in3f", "url": "http://example.com",
             "alarmMinutes": 20, "noShutdown": True, "logging": None,
         }), \
         patch("pyinkdisplay.pyInkPictureFrame.setupLogging"), \
         patch("pyinkdisplay.pyInkPictureFrame.PyInkDisplay") as mock_display, \
         patch("pyinkdisplay.pyInkPictureFrame.fetchImageFromUrl", return_value=MagicMock()), \
         patch("pyinkdisplay.pyInkPictureFrame.PiSugarAlarm") as mock_alarm_cls, \
         patch("pyinkdisplay.pyInkPictureFrame.runBatteryMode") as mock_battery, \
         patch("pyinkdisplay.pyInkPictureFrame.continuousEpdUpdateLoop") as mock_usb:

        mock_args.return_value.config = None
        mock_alarm = MagicMock()
        mock_alarm.isSugarPowered.return_value = True
        mock_alarm_cls.return_value = mock_alarm

        pyInkPictureFrame()

    mock_usb.assert_called_once()
    mock_battery.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_calls_runBatteryMode_when_not_powered tests/test_py_ink_picture_frame.py::test_pyInkPictureFrame_calls_continuousLoop_when_powered -v
```

Expected: FAIL — `runBatteryMode` is defined but the main function still uses the old inline shutdown logic.

- [ ] **Step 3: Refactor `pyInkPictureFrame()` to use `runBatteryMode()`**

Replace the existing body of `pyInkPictureFrame()` from the `alarmManager = PiSugarAlarm()` line through the end of the try block with:

```python
        alarmManager = PiSugarAlarm()

        if alarmManager.isSugarPowered():
            logging.info("PiSugar is powered. Publishing battery level and entering continuous update mode.")
            publishBatteryLevel(alarmManager, mqttConfig)
            continuousEpdUpdateLoop(
                displayManager,
                alarmManager,
                merged["url"],
                merged["alarmMinutes"],
                mqttConfig,
            )
        else:
            logging.info("PiSugar is on battery. Running one-shot battery mode.")
            runBatteryMode(alarmManager, merged["alarmMinutes"], mqttConfig, merged["noShutdown"])
```

Remove the old alarm-setting block that appeared before the `isSugarPowered()` check, and remove the old `elif not merged["noShutdown"]: subprocess.run(["sudo", "shutdown", "+1"], ...)` block — these are now handled inside `runBatteryMode()` and `continuousEpdUpdateLoop()`.

- [ ] **Step 4: Run all tests to verify they pass**

```bash
pytest -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add pyinkdisplay/pyInkPictureFrame.py tests/test_py_ink_picture_frame.py
git commit -m "refactor: use runBatteryMode() in main loop; change shutdown to immediate"
```
