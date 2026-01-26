# Automatically skip Youtube ads

### chromium

run: <br>
```python youtube-add-skipper.py```

opens a separate browser using chromium extension and in that browser will automatically skip ads. <br>
<br>
testing so far:
* running the script opens the new browser and automatically skips ads
* tested in non-fullscreen mode

<br>

### native

run the native: <br>
```python youtube-skipper-native.py```

usable in regular chrome browser. <br>
<br>
testing so far:
* successfully skipped ad on regular chrome browser when watching video in non-fullscreen mode on Macbook Pro
* only worked on laptop screen not on connected monitor



<br><br><br>

# Before starting either

make sure to run from venv or using interpreter after doing ```pip install -r requirements.txt```