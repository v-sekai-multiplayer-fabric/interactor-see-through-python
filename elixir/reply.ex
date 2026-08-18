defmodule Weft.Reply do
  @moduledoc """
  Decodes an interactor's reply into the term a caller matches on.

  RFD 0124 carries the reply in CBOR and states the mapping: tag 39 is an atom, an array is a
  tuple, a map is a map, a text string is a binary. This module is the only place that mapping
  is written, which is the answer to the objection that CBOR needs an adapter -- it needs one,
  and there is one, rather than one per caller.

      iex> Weft.Reply.decode!(bytes)
      {:error, {:res_below_minimum, %{got: 512, minimum: 1280}}}

  Atoms go through `String.to_existing_atom/1`, so a reason this virtual machine does not
  already have raises rather than growing the atom table. That is the guarantee
  `:erlang.binary_to_term/2`'s `[:safe]` gives, written here instead of relied upon. The atoms a
  caller can decode are the ones it names in its own clauses, which is exactly the set it can
  act on.
  """

  @tag_identifier 39

  @doc "Decodes one reply. Raises if the bytes are not a reply this contract describes."
  def decode!(binary) when is_binary(binary) do
    {term, rest} = item(binary)

    if rest != <<>> do
      # Trailing bytes mean the writer and this reader disagree about a length. Absorbing them
      # would turn a truncated reply into a short one, which is a wrong answer, not an error.
      raise ArgumentError, "#{byte_size(rest)} bytes left over after the reply"
    end

    term
  end

  defp item(<<head, _::binary>> = bin) do
    {value, rest} = argument(bin)

    case Bitwise.bsr(head, 5) do
      0 -> {value, rest}
      1 -> {-1 - value, rest}
      3 -> text(rest, value)
      4 -> tuple(rest, value)
      5 -> map(rest, value)
      6 -> tagged(rest, value)
      major -> raise ArgumentError, "major type #{major} is not in a reply"
    end
  end

  defp argument(<<head, rest::binary>>) do
    case Bitwise.band(head, 0x1F) do
      n when n < 24 -> {n, rest}
      24 -> <<v, r::binary>> = rest; {v, r}
      25 -> <<v::16, r::binary>> = rest; {v, r}
      26 -> <<v::32, r::binary>> = rest; {v, r}
      27 -> <<v::64, r::binary>> = rest; {v, r}
      _ -> raise ArgumentError, "indefinite length is not in a reply"
    end
  end

  defp text(rest, n) do
    <<s::binary-size(^n), r::binary>> = rest
    {s, r}
  end

  # An array is a tuple. A reply carries no lists, so this needs no second rule.
  defp tuple(rest, n) do
    {items, r} = take(rest, n, [])
    {List.to_tuple(items), r}
  end

  defp map(rest, n) do
    {flat, r} = take(rest, n * 2, [])
    {flat |> Enum.chunk_every(2) |> Map.new(fn [k, v] -> {k, v} end), r}
  end

  defp tagged(rest, @tag_identifier) do
    {name, r} = item(rest)
    {String.to_existing_atom(name), r}
  end

  defp tagged(_rest, tag), do: raise(ArgumentError, "tag #{tag} is not one a reply uses")

  defp take(rest, 0, acc), do: {Enum.reverse(acc), rest}

  defp take(rest, n, acc) do
    {v, r} = item(rest)
    take(r, n - 1, [v | acc])
  end
end
