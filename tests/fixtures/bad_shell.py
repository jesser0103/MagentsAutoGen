import subprocess

# B602: subprocess call with shell=True — HIGH severity
command = input("Command to execute: ")
result = subprocess.run(command, shell=True)
print(result.returncode)
