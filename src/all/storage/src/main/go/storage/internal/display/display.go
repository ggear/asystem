package display

type Row struct {
	Host       string
	Mount      string
	Size       uint64
	Free       uint64
	Used       uint64
	Percent    float64
	Unmeasured bool
	NewHost    bool
	NewClass   bool
}

const (
	headerHost  = "HST"
	headerMount = "MOUNT"
	headerSize  = "SIZE"
	headerFree  = "FREE"
	headerUsed  = "USED"
)
