# CALIPER on a phone

Three surfaces, in the order of how little they ask of the person holding the
device. All three reach the same backend, so there is one run, one instrument and
one audit trail regardless of which one you use.

## 1. The web app, installed to a home screen

Nothing to install, no store, no account, no review queue.

Open **https://caliper-77ma.onrender.com** on the phone, then Share, then Add to
Home Screen on iOS, or the install prompt on Android. It opens fullscreen with no
browser chrome, with its own icon.

This is the surface a judge should be handed, because scanning a code is the
whole setup.

The microphone works here, because the address is HTTPS and a microphone needs a
secure context. A plain `http://` LAN address does not qualify and will show a
call screen that silently captures nothing.

## 2. The Android app

Signed release builds are published as GitHub Release assets, which have no
retention clock, unlike a build service URL.

**https://github.com/StephenSook/caliper/releases**

Download the APK, allow installs from your browser or file manager when Android
asks, and open it. It connects on its own and goes straight to the call. Verify
the download first if you like:

```
shasum -a 256 caliper-1.0.2-android.apk
```

## 3. The iOS app, on your own phone

Everything is configured. This needs a physical device attached, which is the one
thing that cannot be done from here.

```
# 1. Plug the iPhone into the Mac, unlock it, and trust the computer.
xcrun devicectl list devices          # the phone should appear

# 2. Build and install. --allowProvisioningUpdates lets Xcode mint the device
#    profile on its own against the team already configured in ios/debug.xcconfig.
cd mobile
xcodebuild -project ios/App/App.xcodeproj -scheme App \
  -destination 'platform=iOS,name=<the phone as devicectl prints it>' \
  -allowProvisioningUpdates build

# 3. First launch only: Settings, General, VPN and Device Management, and trust
#    the developer certificate.
```

**TestFlight is deliberately not used, and it is worth saying why out loud rather
than implying it was an option.** External TestFlight testers require Beta App
Review, whose queue is one to two days and is not under our control, so judges
could never have installed it inside this window. Internal testers skip review
entirely, but they have to be App Store Connect users on the team, which is not
something to do at a judging table. A direct device install gives the same
result, in minutes, with no queue. That is an accepted loss with a reason, not an
oversight.

## What the app actually is

A thin launcher around the real product. It holds no product logic and no data.

It exists for one reason: a native binary that hardcodes its backend address is a
time bomb. A development tunnel gets a new hostname on every restart, and the
binary on the phone cannot be rebuilt at a judging table. So the address lives in
device storage, defaults to the permanent instance, is verified with a real
request before anything navigates, and is replaceable in ten seconds.

Because the shell is thin, a change to the product reaches the installed app on
the next launch with no rebuild and no reinstall.

It refuses a plain `http://` address outright. The alternative failure is a call
screen that looks fine and captures nothing.

## The two device demo

The phone is the handset and the laptop is the evidence.

1. The laptop runs the audit and a human approves the diagnosis.
2. The phone attaches itself to that run within a few seconds, untouched.
3. The person holding the phone takes the drill while the laptop shows the
   rewritten quality form filling in, criterion by criterion.

Measured: a run started on the host appeared on the phone in under eight seconds
with nobody touching the phone.

The phone can also start the audit itself, through the same product path rather
than a shortcut, for when it is the only device in hand.

## Permissions

Android declares `RECORD_AUDIO` and `MODIFY_AUDIO_SETTINGS`. iOS declares
`NSMicrophoneUsageDescription`. On iOS the missing string is not a permission
denial: the process is terminated outright, with no dialog and no error, so the
app simply disappears.
