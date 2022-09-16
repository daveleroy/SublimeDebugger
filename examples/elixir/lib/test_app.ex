defmodule TestApp do
  use Application

  def start(_type, _args) do
    IO.puts("starting")

    Task.start(fn -> IO.puts("task") end)
  end
end
