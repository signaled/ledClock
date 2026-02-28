# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python project for discovering and controlling IDM-brand Bluetooth Low Energy (BLE) LED pixel display devices. Uses the `bleak` library for BLE communication with async/await patterns.

## Setup

```bash
pip install bleak
```

## Running

```bash
python scan.py
```

## Architecture

- `scan.py` — BLE scanner that discovers nearby IDM-* devices, connects to each, and enumerates their GATT services and characteristics
- All BLE communication is async using `asyncio` and `bleak.BleakClient` context managers
- Device filtering is by name prefix "IDM-"

## Conventions

- Comments and user-facing strings are in Korean
