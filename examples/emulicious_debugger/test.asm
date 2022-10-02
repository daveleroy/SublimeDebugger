DEF rLCDC EQU $FF40
DEF rLY EQU $FF44
DEF rBGP EQU $FF47
DEF rIE EQU $FFFF

SECTION "VBlank", ROM0[$40]
	reti

SECTION "Header", ROM0[$100]
Entry:
	di
	jp Main
	ds $150 - @, 0

SECTION "Main", ROM0
Main:
	ldh a, [rLY]
	cp a, 144
	jr c, Main
	xor a, a
	ldh [rLCDC], a
	ldh [rBGP], a
	inc a
	ldh [rIE], a

	ld bc, Font.end - Font
	ld de, Font
	ld hl, $8000 + 16 * 32
.copy
	ld a, [de]
	inc de
	ld [hli], a
	dec c
	jr nz, .copy
	dec b
	jr nz, .copy

	ld de, wScriptPool
	ld hl, TestScript
	call ExecuteScript
	ld a, %10010001
	ldh [rLCDC], a
	ei
.forever
	halt
	ld de, wScriptPool
	call ExecuteScript
	jr .forever

SECTION "Print Function", ROM0
PrintFunction:
	push hl
	ld a, [hli]
	ld h, [hl]
	ld l, a
	ld de, $9800 + 32
.next
	ld a, [hli]
	and a, a
	jr z, .exit
	ld [de], a
	inc de
	jr .next

.exit
	pop hl
	inc hl
	inc hl
	ret

SECTION "Font", ROM0
Font:
	INCBIN "bin/font.2bpp"
.end

DEF swap_bank EQUS "ld [$2000], a"
INCLUDE "../src/runtime/evsbytecode.asm"
INCLUDE "../src/runtime/driver.asm"
	; After including the driver, define the jump table.
	std_bytecode
	dw PrintFunction

INCLUDE "bin/script.asm"

SECTION "Script Pool", WRAM0
wScriptPool: ds 16