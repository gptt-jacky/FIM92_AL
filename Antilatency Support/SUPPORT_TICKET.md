# Antilatency Support Ticket

## Summary

**[C++ SDK 4.5.0] Alt Tracking cotask fails when Hardware Extension cotask creates 2 output pins on the same physical Socket**

---

## Environment

| Item | Details |
|------|---------|
| Antilatency SDK | 4.5.0 (Rev.367) |
| OS | Windows 11 (64-bit) |
| Compiler | MSVC 2019+, C++17 |
| Software | C++ SDK application |
| Connection | USB direct and URS wireless (https://developers.antilatency.com/Hardware/Universal_Radio_Socket_en.html) |

---

## What We Are Trying to Do

We are building a C++ application that combines functionality from two official Antilatency examples:

1. **TrackingMinimalDemoCpp** - https://developers.antilatency.com/HowTo/TrackingMinimalDemoCpp_en.html
2. **ExtensionInterface StarterKit Demo App** - https://developers.antilatency.com/Software/Tools/ExtensionInterfaceStarterKitDemoApp_en.html

Our goal is to run these two cotasks simultaneously on the same physical Socket device:

1. **Alt Tracking cotask**
2. **Hardware Extension Interface cotask**

The HW Extension configuration under test is:

- 6 input pins: IO1, IO2, IOA3, IOA4, IO5, IO6
- 2 output pins: IO7 and IO8

In our application, `altNode` and `hwNode` are separate child node handles that belong to the same physical Socket. We match them by comparing `network.nodeGetParent()`.

---

## What We Observed

When the HW Extension cotask creates 2 output pins before starting the Alt Tracking cotask, the Alt Tracker does not start correctly:

- LED does not turn green (it stays orange or off)
- `getExtrapolatedState()` does not produce valid 6DOF tracking data
- Stability stays at 0 or 1
- No exception is thrown
- Removing the second output pin restores normal Alt Tracking immediately

### Test Matrix

| Configuration | Result |
|---|---|
| 6 input (IO1-IO6) + IO7 output + IO8 output + Alt Tracker | FAIL - Alt Tracking does not start |
| IO7 output + IO8 output with try/catch fallback + Alt Tracker | FAIL - no exception, Alt Tracking still does not start |
| IO6 output + IO7 output + Alt Tracker | FAIL - same behavior |
| 5 input + IO7 output + IO8 output + Alt Tracker | FAIL - same behavior |
| 7 input + IO7 output only + Alt Tracker | PASS - works normally |
| IO7 output + IO8 output with no Alt Tracker (HW Extension only) | PASS - works normally |

Based on these tests, the failure appears to be specific to this combination:

```text
Alt Tracking cotask + Hardware Extension cotask + 2 output pins
on the same physical Socket / same parent node
```

### Minimal Code Pattern

```cpp
// PASS: 1 output only - Alt Tracker starts normally
hwCotask.createOutputPin(Pins::IO7, PinState::Low);
hwCotask.run();
auto altCotask = altConstructor.startTask(network, altNode, env);

// FAIL: 2 outputs - Alt Tracker does not start
hwCotask.createOutputPin(Pins::IO7, PinState::Low);
hwCotask.createOutputPin(Pins::IO8, PinState::Low);
hwCotask.run();
auto altCotask = altConstructor.startTask(network, altNode, env);
```

A standalone C++ reproduction program is attached: `MinimalReproduction.cpp`.

This reproduction is intentionally focused on the C++ SDK behavior. It does not require our Python monitor, WebSocket server, or application-specific logic.

---

## Questions for Antilatency

Could you confirm whether this configuration is officially supported?

```text
Alt Tracking cotask + Hardware Extension cotask + 2 output pins
on the same physical Socket / same parent node
```

If it is supported:

1. Is there a required API call order or device configuration we are missing?
2. Is there a recommended way to allocate two output pins while Alt Tracking is running on the same physical Socket?

If it is not supported:

1. Could you confirm the limitation so we can document our architecture correctly?
2. Should the SDK report an error, return null, or throw an exception instead of allowing Alt Tracking to fail silently?

## Future Hardware Requirement

In our future hardware design, we may need **3 output pins** while Alt Tracking is running on the same physical Socket.

Could you also clarify the official output-pin limit when Alt Tracking cotask is active?

Specifically:

1. Is the practical limit exactly 1 output pin with Alt Tracking?
2. Are 2 or 3 output pins unsupported by design?
3. Is the limit caused by firmware resources, Socket hardware resources, or SDK cotask scheduling?
4. Is there any device, firmware, or recommended architecture that supports Alt Tracking plus 3 output pins on the same physical Socket?
5. If same-device Alt Tracking + 3 output pins is not supported, is the recommended design to split outputs to a separate IO-only Socket / Extension device?

The Extension Module documentation (https://developers.antilatency.com/Hardware/ExtensionModule_en.html) says every IO pin supports output mode, and the StarterKit Demo shows 2 output-type pins working. However, we could not find documentation about using 2 output pins while Alt Tracking is running on the same physical Socket.

Any guidance would be appreciated.
