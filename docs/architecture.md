# Architecture

`pdf-cleanup` is a self-contained tool run through `run.sh`.

## Flow

```
run.sh [args]  →  (your tool)
```

`run.sh` resolves its own directory so it works from any caller, then
invokes the tool. Add implementation files beside it and document any
runtime dependencies.
