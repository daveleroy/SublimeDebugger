
FONT_SIZE = 1
HEIGHT = 1.5
WIDTH = 1.5
LABEL_OFFSET = 1.5
INLINE_PADDING_TOP = 0.5
INLINE_PADDING_BOTTOM = 0.1
IMG_OFFSET = 0.1


def css() -> str:
	return '''
	body {
		padding: 1px;
		line-height: 1.0rem;
		font-size: 1rem;
		--height: 1.5rem;
		--width: 1.5rem;
		--label-offset: 0.35rem;
		--box-padding-top: 0.45rem;
		--box-padding-bottom: -0.2rem;
	}
	'''
