# Mock sampling fixture

`create-message.jsonl` provides a canned response for the local Executa
harness. Run it through the project wrapper:

```text
pnpm executa:dev
```

The fixture matches `sampling/createMessage` requests containing the sample
customer follow-up text. The protocol integration test in
`tests/test_executa_protocol.py` exercises the same reverse-RPC path without
requiring an Anna account.
