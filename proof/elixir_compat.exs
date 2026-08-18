# The authoritative check on RFD 0124: a real virtual machine decodes what this interactor
# writes, through the one decoder the contract ships, and a caller matches the result.
#
# proof/test_command.py asserts the same terms with a Python reader. That is cheap and runs
# anywhere, and it cannot establish this: a Python decoder agreeing with a Python encoder proves
# the pair agree, not that either speaks Elixir.
#
#     python3 proof/write_replies.py /tmp/replies && elixir proof/elixir_compat.exs /tmp/replies

Code.require_file("elixir/reply.ex", File.cwd!())

dir = System.argv() |> List.first() || "/tmp/replies"
failures = :counters.new(1, [])

check = fn name, ok? ->
  IO.puts("#{if ok?, do: "ok  ", else: "FAIL"} #{name}")
  unless ok?, do: :counters.add(failures, 1, 1)
end

read = fn file -> Weft.Reply.decode!(File.read!(Path.join(dir, file))) end

# Naming the atoms in these clauses is what makes them exist, which is what lets
# to_existing_atom decode them. The set a caller can read is the set it has a clause for.
check.("a refusal is {:error, {:res_below_minimum, %{got: _, minimum: _}}}",
  match?({:error, {:res_below_minimum, %{got: 512, minimum: 1280}}}, read.("res.cbor")))

check.("a bare reason is {:error, :no_engine}",
  match?({:error, :no_engine}, read.("no_engine.cbor")))

check.("a success is {:ok, map} with atom keys",
  match?({:ok, %{layers: 7, ms: 359_000, sidecar: "res.psd.json"}}, read.("ok.cbor")))

check.("an unknown command names the verb",
  match?({:error, {:unknown_command, %{verb: "render"}}}, read.("verb.cbor")))

{:error, reason} = read.("res.cbor")
check.("a reason is a tuple of an atom and a map",
  match?({r, m} when is_atom(r) and is_map(m), reason))

{:ok, value} = read.("ok.cbor")
check.("every key of the value is an atom", Enum.all?(Map.keys(value), &is_atom/1))
check.("integers arrive as integers", is_integer(value.ms) and is_integer(value.layers))
check.("text arrives as a binary", is_binary(value.sidecar))

# A reason no module names must not be decodable, or the closed set is not closed.
novel = <<0x82, 0xD8, 39, 0x65, "error", 0xD8, 39, 0x6A, "never_seen">>
check.("a reason no caller names is refused, not created",
  match?({:error, _}, (try do
    {:ok, Weft.Reply.decode!(novel)}
  rescue
    ArgumentError -> {:error, :refused}
  end)))

n = :counters.get(failures, 1)
IO.puts(if n == 0, do: "elixir_compat: all checks passed", else: "elixir_compat: FAILED")
System.halt(if n == 0, do: 0, else: 1)
