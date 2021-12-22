defmodule TestApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :test_app,
      version: "0.0.0"
    ]
  end

  def application do
    [
      mod: {TestApp, []}
    ]
  end
end
