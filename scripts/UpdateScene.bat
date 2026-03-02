@echo off
title Antilatency Scene Manager
chcp 65001 >nul
cd /d "%~dp0.."
python scripts\update_scene.py
