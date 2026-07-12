@echo off
echo Installing MySQL as Windows service...
"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --install MySQL --defaults-file="C:\ProgramData\MySQL\MySQL Server 8.4\my.ini"
if %errorlevel% equ 0 (
    echo Service installed. Starting...
    net start MySQL
    echo Done.
) else (
    echo Install failed. Trying sc create...
    sc create MySQL binPath= "\"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe\" --defaults-file=\"C:\ProgramData\MySQL\MySQL Server 8.4\my.ini\"" start= auto DisplayName= "MySQL 8.4"
    net start MySQL
    echo Attempted.
)
