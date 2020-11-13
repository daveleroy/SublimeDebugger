// let test2 = require('./test_test_test_test_test_test.js')

console.log('env')
console.log('env')

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


// let blobURL = URL.createObjectURL( new Blob([ '(',

// function(){
//     console.log("From worker")
// }.toString(),

// ')()' ], { type: 'application/javascript' } ) )

// // let myWorker = new Worker(blobURL);
// // console.log("From worker")


// function test() {
// 	console.log("TEST")
// 	s = ""
// 	while (s.length < 100000000) {
// 		s += "asdfas"
// 	}
// }

// test()

// const { Worker, isMainThread } = require('worker_threads');

// if (isMainThread) {
//   // This re-loads the current file inside a Worker instance.
//   new Worker(__filename);

//   console.log('outside');
//   console.log('outside')
//   function function2() {
//   	console.log('Inside Worker!');
//   }
//   setTimeout(function2, 10000);;
// } else {
//   console.log('Inside Worker!');
//   console.log(isMainThread);  // Prints 'false'.
// }