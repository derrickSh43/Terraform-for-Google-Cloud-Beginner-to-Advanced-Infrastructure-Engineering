# Troubleshooting 14 — "The dead-letter queue is always empty"

A bug in the worker makes it fail on orders with gift cards. The team expected
those orders to land in `orders-dead-letter-inspect` after 5 attempts. Instead:

- the dead-letter subscription stays empty;
- the push subscription's backlog keeps growing;
- the worker logs show the same order IDs failing again and again, for days.

`max_delivery_attempts = 5` is clearly set.

```powershell
Copy-Item -Recurse lessons/14-event-driven/broken workspace/14-broken
python course.py check 14 --path workspace/14-broken
```

1. Which requirement fails? Who actually moves a message to the dead-letter topic?
2. What happens when that identity isn't allowed to publish there?
3. Fix it. Which *two* grants does dead-lettering need, and on which resources?
4. Why would this never show up as an error in `terraform apply`?

Answer: [ANSWER.md](ANSWER.md)
