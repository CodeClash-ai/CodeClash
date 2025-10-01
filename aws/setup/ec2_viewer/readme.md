# Start ec2 viewer

## Starting instance

* Make sure to tick http and https access
* Should appear as inbound rules in security group

## Associate elastic IP with instance

## Installing stuff

Mostly follow sync.sh

## Starting server

Make sure to replace

```
app.run(debug=True, host="0.0.0.0", port=5001)
```

with

```
app.run(debug=False, host="127.0.0.1", port=5001)
```

## Debugging

* `http://emagedoc.xyz/` and same with IP should show nginx default page "needs configuration"
* `http://emagedoc.xyz/` is working but https is not -> check cerbot
