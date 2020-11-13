
package main

import "fmt"
import "time"

func main() {
	a := "Some string variable"
	b := 123
	c := 3.0
	d := [] int {1, 2, 3}
	fmt.Println(a)
	fmt.Println(b)
	fmt.Println(c)
	fmt.Println(d)
	fmt.Println("Waiting for 3 seconds")
	time.Sleep(3 * time.Second)
	fmt.Println("Done")
}