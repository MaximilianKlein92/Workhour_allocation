MAX_DAYS = 31
MAX_BUCKETS = 10
BUCKET_NAMES = list("ABCDEFGHIJ")
DEFAULT_BUCKET_COUNT = 2
DEFAULT_PERCENT_VALUES = [20.0, 80.0] + [0.0] * 8
MAX_SEGMENTS_PER_DAY = 2

# Central color palette for projects A-J. Use these consistently across the app.
BUCKET_COLORS = [
	"#2563eb",
	"#16a34a",
	"#dc2626",
	"#fde400",
	"#c304caa0",
	"#e98b21",
	"#fc7302ab",
	"#000000",
	"#ffffff",
	"#65d5f1",
]

# Matching emoji markers for projects A-J. These are used as the visible project signatures in the UI.
BUCKET_EMOJIS = [
	"🔵",
	"🟢",
	"🔴",
	"🟡",
	"🟣",
	"🟠",
	"🟤",
	"⚫",
	"⚪",
	"🩵",
]
