let integer = 25;
let string = "string"
let array = [1, 2, 3, "One", "Two", "Three"]

let object = {
	a: 1,
	b: "Two",
	c: [1, 2, 3]
} 

try {
	throw "A test exception";
}
catch (e) {
}
function SomeFunction(argument) {
	console.log(integer)
	console.log(string)
	console.log(array)
	console.log(object)
}
function SomeOuterFunctions(argument) {
	console.log(integer)
	console.log(string)
	console.log(array)
	SomeFunction()
}

SomeOuterFunctions()