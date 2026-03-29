# Moomoo OpenD Setup Guide

This document explains how to set up Moomoo's OpenD daemon, which is required for accessing live account balances and positions.

## What is OpenD?

**OpenD** is Moomoo's local daemon (background service) that provides access to market data and account information. It runs on your machine on `localhost:11111` by default.

The system **does not** use REST API calls to Moomoo. Instead, it uses the official Moomoo Python SDK (`moomoo-api`), which connects to the local OpenD daemon via binary protocol.

## Installation

1. **Download OpenD**
   - Visit: https://www.moomoo.com/download/OpenAPI
   - Download the latest version for your OS (Windows, macOS, Linux)

2. **Install**
   - Run the installer and follow on-screen instructions
   - Choose default installation path

3. **Start OpenD**
   - Open the Moomoo OpenD application
   - Log in with your Moomoo account
   - Wait for it to fully load (may take 30 seconds)
   - You should see a status like "Ready" or "Connected"

## Verify Connection

Test that OpenD is running on the correct port:

### Windows PowerShell
```powershell
# Check if port 11111 is open
Get-NetTCPConnection -LocalPort 11111 -ErrorAction SilentlyContinue | Select-Object State, LocalPort, OwningProcess
```

### macOS / Linux
```bash
# Check if port 11111 is listening
lsof -i :11111
# or
netstat -tuln | grep 11111
```

## Python Configuration

In your `.env` file:

```env
MOOMOO_OPEND_HOST=127.0.0.1
MOOMOO_OPEND_PORT=11111
```

The default values in the codebase are already `127.0.0.1:11111`, so you only need to override these if your OpenD is running on a different machine or port.

## Troubleshooting

### OpenD won't start or crashes on launch

**Solution**:
1. Restart your computer
2. Re-install OpenD from https://www.moomoo.com/download/OpenAPI
3. Check system resources (RAM, disk space)
4. Review OpenD logs (usually in the installation directory)

### "Connection refused" error when running scans

**Likely cause**: OpenD daemon isn't running or closed unexpectedly.

**Solution**:
1. Open the Moomoo OpenD application again
2. Log in (same credentials as your Moomoo account)
3. Wait for it to fully initialize
4. Keep it running in the background while the scanner is active

### Scanner can't access account bala nces or positions

**Check these in order**:
1. OpenD is running and logged in
2. Your Moomoo account has trading/margin enabled
3. The account hasn't been locked or suspended
4. Try refreshing OpenD (close and reopen)
5. Check logs in the OpenD application

### Port 11111 is already in use

**Cause**: Another application is using the port, or OpenD is running on a different computer.

**Solution**:
1. Find what's using port 11111 and close it
2. Or, run OpenD on a different machine and update `.env`:
   ```env
   MOOMOO_OPEND_HOST=192.168.1.100  # IP of machine running OpenD
   MOOMOO_OPEND_PORT=11111
   ```

## Running OpenD on a Remote Machine (Optional)

If you have OpenD running on another machine on your network:

1. Install OpenD on that machine
2. Configure it to accept remote connections (check its settings)
3. Update `.env` in the scanner with that machine's IP:
   ```env
   MOOMOO_OPEND_HOST=192.168.1.50
   MOOMOO_OPEND_PORT=11111
   ```
4. Ensure network connectivity between your scanner machine and the OpenD machine

## Reference

- Official Moomoo OpenAPI Documentation: https://openapi.moomoo.com/moomoo-api-doc/en/
- Python SDK: `pip list | grep moomoo-api`
- OpenD FAQ: Check the Moomoo OpenD application Help menu

---

**Note**: OpenD must be left running while the scanner is active (especially if using the scheduler). Consider starting it at system boot or using its persistent mode.
