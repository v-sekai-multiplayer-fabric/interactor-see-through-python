# The authoritative check on RFD 0124: a real virtual machine decodes what this interactor
# writes, and a caller matches it with no translation step.
#
# proof/test_command.py asserts the same terms with a Python reader, which is cheap and runs
# anywhere. It cannot establish this: a Python decoder agreeing with a Python encoder proves the
# pair agree, not that either speaks Erlang. This file is the one that answers that.
#
#     python3 proof/write_replies.py /tmp/replies && elixir proof/elixir_compat.exs /tmp/replies

dir = System.argv() |> List.first() || "/tmp/replies"
failures = :counters.new(1, [])

check = fn name, ok? ->
  IO.puts("#{if ok?, do: "ok  ", else: "FAIL"} #{name}")
  unless ok?, do: :counters.add(failures, 1, 1)
end

read = fn file ->
  # [:safe] refuses to create an atom this virtual machine does not have. Every atom below
  # exists because this file names it, which is the property RFD 0124 rests on.
  :erlang.binary_to_term(File.read!(Path.join(dir, file)), [:safe])
end

check.("a refusal is {:error, {:res_below_minimum, %{got: _, minimum: _}}}",
  match?({:error, {:res_below_minimum, %{got: 512, minimum: 1280}}}, read.("res.etf")))

check.("a bare reason is {:error, :no_engine}",
  match?({:error, :no_engine}, read.("no_engine.etf")))

check.("a success is {:ok, map} with atom keys",
  match?({:ok, %{layers: 7, ms: 359_000, sidecar: "res.psd.json"}}, read.("ok.etf")))

check.("an unknown command names the verb",
  match?({:error, {:unknown_command, %{verb: "render"}}}, read.("verb.etf")))

# The shapes a GenServer caller writes. If these compile and match, the reply needs no adapter.
{:error, reason} = read.("res.etf")
check.("a reason is a tuple of an atom and a map", match?({r, m} when is_atom(r) and is_map(m), reason))

{:ok, value} = read.("ok.etf")
check.("every key of the value is an atom", Enum.all?(Map.keys(value), &is_atom/1))
check.("integers arrive as integers", is_integer(value.ms) and is_integer(value.layers))
check.("text arrives as a binary", is_binary(value.sidecar))

n = :counters.get(failures, 1)
IO.puts(if n == 0, do: "elixir_compat: all checks passed", else: "elixir_compat: FAILED")
System.halt(if n == 0, do: 0, else: 1)
