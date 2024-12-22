// Build the project first either by running `dotnet build` or by using the sublime build system
public static class Program {
	public static void Main() {
		int a = 5;
		for (int i = 0; i < 100000; i++) {
			a += i;
		}
		Console.WriteLine(a);
	}
}
