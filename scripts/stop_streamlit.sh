# #!/bin/bash
# #APP_Name=streamlit
# APP_PID=$(pgrep streamlit)

# if [ -z "$APP_PID" ];
# then
#   echo "Application is not running"
# else
#   echo "Kill -9 $APP_PID"
#   kill -9 "$APP_PID"
#   sleep 5
# fi

# exit 0

#!/bin/bash

APP_NAME="streamlit"
APP_PID=$(pgrep "$APP_NAME")

if [ -n "$APP_PID" ]; then
  echo "Killing process: $APP_PID"
  kill -9 "$APP_PID" || echo "Failed to kill process $APP_PID"
  sleep 2
else
  echo "No $APP_NAME process is running"
fi

exit 0
