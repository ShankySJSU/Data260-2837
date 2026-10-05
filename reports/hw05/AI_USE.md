AI_USE.md – HW5

# DATA260 HW5 AI Use Disclosure

1. What I used an AI assistant for and what I did myself: 

I used AI for code validation and issues resolution and also drafting the final report. I used an AI assistant to help understand the HW5 requirements, plan the software architecture, extend the existing HW4
I did all the execution, and you can see my “last 4 digit of student ID (018322837) i.e. 2837 in every output and execution. 
I used my own existing HW4 repository, database, credentials, local
environment, and assigned domain data. I manually created the files in my
repository, executed the commands, tested the application, reviewed the
outputs, and captured the required evidence screenshots.

2. One AI-produced output that was wrong or unsuitable: My verification result was getting wrong specifically for “backend server” running health check. And AI was giving all kinds of explanation that why your server is not running etc.
3. How I detected it: I reviewed my outputs and everything looked good to me. Moreover, all my earlier tests and processes were working fine, hence I was sure my code/applications were working fine. I once again reviewed my  verification.py code and realized that something is not right.
4. What I changed and why it works now:  I looked closely at my “check_backend_running” method and there was a typo in my status_code. Instead of 200 it was “280”. Once I fixed it, all my validation passed.



