let integer = 25;
let string = "string"
let array = [1, 2, 3, "One", "Two", "Three"]
let object = {
	a: 1,
	b: "Two",
	c: [1, 2, 3]
}

let buffer = new ArrayBuffer(2048)

let a = object.a
let b = object.b
let c = object.c

console.log(a, b, c)

try {
	throw new Error("Caught Exception");
}
catch (e) {
	// ignore
}

console.log(integer)
console.info(integer)
console.warn(integer)
console.error(integer)

console.log(string)
console.info(string)
console.warn(string)
console.error(string)

console.log(object)
console.info(object)
console.warn(object)
console.error(object)

console.group('group begin')
console.log('a')
console.log('b')
console.log('c')

console.group('group begin')
console.log('a')
console.log('b')
console.log('c')
console.groupEnd()

console.groupCollapsed('group collapsed begin')
console.log('a')
console.log('b')
console.log('c')

console.groupEnd()
console.groupEnd()


// throw "Uncaught Exception"

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