# MySQL Backup Procedure

This document describes how to back up the IPO Checker database securely.

## Prerequisite
- You must have `mysqldump` installed and available in your system's PATH.
- The `IPO_Checker/backend/.env` file must be populated with your MySQL credentials.

## Running Backups Manually
You can run the backup script manually using PowerShell:
```powershell
cd IPO_Checker/backend/scripts
.\backup.ps1
```
This will create a `.sql` dump file in the `IPO_Checker/backend/scripts/backups/` directory.

## Automated Backups (Windows Task Scheduler)
To ensure backups run automatically (e.g., daily):

1. Open **Task Scheduler**.
2. Click **Create Basic Task...**
3. Name it "IPO Checker Database Backup".
4. Set the trigger to **Daily**.
5. Set the Action to **Start a program**.
6. Set Program/script to `powershell.exe`.
7. Set Add arguments to: `-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\path\to\project_ipo\IPO_Checker\backend\scripts\backup.ps1"`
8. Set Start in to: `C:\path\to\project_ipo\IPO_Checker\backend\scripts`
9. Under the task properties, select **Run whether user is logged on or not** and ensure the user running it has permission to read the `.env` file and write to the `backups` directory.

## Access Restrictions
- Store backups on a secure volume.
- Only administrators should have read/write access to the backup directory.
- The `.env` file must be kept secure with restricted read access.
