# Antilatency Service Desk Form Fields

Use this file when filling in the Antilatency Service Desk "Software issues" request.

## Required Identity Fields

```text
Name:
<YOUR NAME>

Organization:
<YOUR ORGANIZATION OR LEAVE BLANK>

Contact Info:
<YOUR EMAIL>
```

## Software Fields

```text
Select your software:
Antilatency Service

Software version:
4.0.0

SDK version:
4.5.0 (Rev.367)

Time Zone:
UTC+8 / Asia/Taipei
```

Note: The form software selector may point to Antilatency Service, but this request is about C++ SDK behavior. The Summary and Description explicitly state that the issue is reproduced in a standalone C++ SDK 4.5.0 program.

## Summary

```text
[C++ SDK 4.5.0] Alt Tracking cotask fails when Hardware Extension cotask creates 2 output pins on the same physical Socket
```

## Description

Copy the full content of:

```text
Antilatency Support/SUPPORT_TICKET.md
```

## Attachment

Attach these files:

```text
Antilatency Support/SUPPORT_TICKET.md
Antilatency Support/MinimalReproduction.cpp
```

Do not attach `RunMonitor.bat` unless Antilatency asks for the full project runtime flow. The minimal reproduction is focused on C++ SDK cotask behavior and does not depend on Python, WebSocket, or monitor scripts.
