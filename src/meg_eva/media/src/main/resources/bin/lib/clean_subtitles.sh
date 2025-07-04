#!/bin/bash

# FFmpeg script to detect and remove erroneous subtitles from MKV files
# Features:
# - Recursively finds all *.mkv files
# - Handles spaces and special characters in filenames
# - Creates new file with __TRANSCODE_1.mkv suffix when problematic subtitles found
# - Detects subtitle issues: short duration, low display rate, empty content
# - Leaves original files untouched

#set -eo pipefail

# Configuration
MIN_SUBTITLE_DURATION=0.5    # Minimum subtitle display duration in seconds
MIN_SUBTITLE_RATE=0.1        # Minimum subtitle entries per second
MAX_EMPTY_SUBS=5             # Maximum number of empty subtitle entries allowed
OUTPUT_SUFFIX="__TRANSCODE_1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    printf "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} %s\n" "$1"
}

error() {
    printf "${RED}[ERROR]${NC} %s\n" "$1" >&2
}

warning() {
    printf "${YELLOW}[WARNING]${NC} %s\n" "$1"
}

success() {
    printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"
}

# Function to check if ffmpeg and ffprobe are available
check_dependencies() {
    if ! command -v ffmpeg &> /dev/null; then
        error "ffmpeg is not installed or not in PATH"
        exit 1
    fi

    if ! command -v ffprobe &> /dev/null; then
        error "ffprobe is not installed or not in PATH"
        exit 1
    fi
}

# Function to get video information
get_video_info() {
    local file="$1"
    local info_json

    if info_json=$(ffprobe -v quiet -print_format json -show_format -show_streams "$file" 2>/dev/null); then
        printf '%s\n' "$info_json"
        return 0
    else
        error "Failed to probe file: $file"
        return 1
    fi
}

# Helper function for safe arithmetic
bc_calc() {
    local expr="$1"
    local result
    if result=$(printf '%s\n' "$expr" | bc -l 2>/dev/null); then
        if [[ -n "$result" && "$result" != "" ]]; then
            printf '%s\n' "$result"
            return 0
        fi
    fi
    printf '0\n'
    return 1
}

# Helper function for floating point comparison
bc_compare() {
    local expr="$1"
    local result
    if result=$(printf '%s\n' "$expr" | bc -l 2>/dev/null); then
        if [[ -n "$result" && "$result" =~ ^[01]$ ]]; then
            return "$result"
        fi
    fi
    return 1
}

# Function to convert SRT time format to seconds
time_to_seconds() {
    local time_str="$1"
    # Format: 00:00:00,000

    # Validate input format
    if [[ ! "$time_str" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}$ ]]; then
        printf '0\n'
        return 1
    fi

    local hours minutes seconds milliseconds
    local seconds_ms

    IFS=':' read -r hours minutes seconds_ms <<< "$time_str" || return 1
    IFS=',' read -r seconds milliseconds <<< "$seconds_ms" || return 1

    # Strip leading zeros to avoid octal interpretation
    hours=$((10#$hours))
    minutes=$((10#$minutes))
    seconds=$((10#$seconds))
    milliseconds=$((10#$milliseconds))

    # Validate that we got numeric values
    if [[ ! "$hours" =~ ^[0-9]+$ ]] || [[ ! "$minutes" =~ ^[0-9]+$ ]] || \
       [[ ! "$seconds" =~ ^[0-9]+$ ]] || [[ ! "$milliseconds" =~ ^[0-9]+$ ]]; then
        printf '0\n'
        return 1
    fi

    # Convert to total seconds using bc directly
    local total_seconds
    if total_seconds=$(printf 'scale=3; %s * 3600 + %s * 60 + %s + %s / 1000\n' \
                    "$hours" "$minutes" "$seconds" "$milliseconds" | bc -l 2>/dev/null); then
        if [[ -n "$total_seconds" && "$total_seconds" != "" ]]; then
            printf '%s\n' "$total_seconds"
            return 0
        fi
    fi
    printf '0\n'
    return 1
}

# Function to convert ASS time format to seconds
ass_time_to_seconds() {
    local time_str="$1"
    # Format: 0:00:00.00

    # Validate input format (more flexible for ASS)
    if [[ ! "$time_str" =~ ^[0-9]+:[0-9]{2}:[0-9]{2}\.[0-9]{2}$ ]]; then
        printf '0\n'
        return 1
    fi

    local hours minutes seconds

    IFS=':' read -r hours minutes seconds <<< "$time_str" || return 1

    # Strip leading zeros to avoid octal interpretation
    hours=$((10#$hours))
    minutes=$((10#$minutes))
    # For seconds with decimal, we need to handle it differently
    # since it's already a decimal number, no need for 10# conversion

    # Validate that we got numeric values
    if [[ ! "$hours" =~ ^[0-9]+$ ]] || [[ ! "$minutes" =~ ^[0-9]+$ ]] || \
       [[ ! "$seconds" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        printf '0\n'
        return 1
    fi

    # Convert to total seconds using bc directly
    local total_seconds
    if total_seconds=$(printf 'scale=3; %s * 3600 + %s * 60 + %s\n' \
                    "$hours" "$minutes" "$seconds" | bc -l 2>/dev/null); then
        if [[ -n "$total_seconds" && "$total_seconds" != "" ]]; then
            printf '%s\n' "$total_seconds"
            return 0
        fi
    fi
    printf '0\n'
    return 1
}

# Function to analyze subtitle timing and content
analyze_subtitle_content() {
    local file="$1"
    local subtitle_index="$2"
    local video_duration="$3"

    # Extract subtitle to temporary file for analysis
    local temp_sub="/tmp/subtitle_${subtitle_index}_$$.srt"
    local temp_ass="/tmp/subtitle_${subtitle_index}_$$.ass"

    # Try to extract as SRT first, then ASS/SSA
    local extraction_success=false

    if ffmpeg -v quiet -i "$file" -map "0:$subtitle_index" -c:s srt "$temp_sub" 2>/dev/null; then
        extraction_success=true
    elif ffmpeg -v quiet -i "$file" -map "0:$subtitle_index" -c:s ass "$temp_ass" 2>/dev/null; then
        temp_sub="$temp_ass"
        extraction_success=true
    fi

    if [[ "$extraction_success" == "false" ]]; then
        rm -f "$temp_sub" "$temp_ass"
        return 1
    fi

    # Analyze subtitle content
    local issues=()

    # Check if file is empty
    if [[ ! -s "$temp_sub" ]]; then
        issues+=("empty_file")
    else
        # Parse subtitle file for timing analysis
        local subtitle_count=0
        local total_duration=0
        local empty_count=0
        local very_short_count=0

        if [[ "$temp_sub" == *.srt ]]; then
            # Parse SRT format
            while IFS= read -r line; do
                # SRT timing line format: 00:00:00,000 --> 00:00:02,000
                if [[ "$line" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}\ --\>\ [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}$ ]]; then
                    ((subtitle_count++))

                    # Extract start and end times
                    local start_time end_time
                    start_time=$(printf '%s' "$line" | cut -d' ' -f1)
                    end_time=$(printf '%s' "$line" | cut -d' ' -f3)

                    # Convert to seconds with error handling
                    local start_sec end_sec duration
                    start_sec=$(time_to_seconds "$start_time" 2>/dev/null || echo "0")
                    end_sec=$(time_to_seconds "$end_time" 2>/dev/null || echo "0")

                    # Only process if both conversions succeeded
                    if [[ "$start_sec" != "0" || "$start_time" == "00:00:00,000" ]] && \
                       [[ "$end_sec" != "0" || "$end_time" == "00:00:00,000" ]]; then

                        duration=$(bc_calc "$end_sec - $start_sec" 2>/dev/null || echo "0")

                        if [[ "$duration" != "0" ]] && [[ "$duration" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                            total_duration=$(bc_calc "$total_duration + $duration" 2>/dev/null || echo "$total_duration")

                            # Check for very short subtitles
                            if bc_compare "$duration < $MIN_SUBTITLE_DURATION" 2>/dev/null; then
                                ((very_short_count++))
                            fi
                        fi
                    fi
                fi

                # Check for empty content lines (lines that are not numbers or timing)
                if [[ -n "$line" && ! "$line" =~ ^[0-9]+$ && ! "$line" =~ ^[0-9]{2}:[0-9]{2}:[0-9]{2} ]]; then
                    if [[ -z "${line// /}" ]]; then
                        ((empty_count++))
                    fi
                fi
            done < "$temp_sub"
        elif [[ "$temp_sub" == *.ass ]]; then
            # Parse ASS/SSA format
            while IFS= read -r line; do
                if [[ "$line" =~ ^Dialogue: ]]; then
                    ((subtitle_count++))

                    # Extract timing from ASS format
                    # Format: Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Text
                    local start_time end_time
                    start_time=$(printf '%s' "$line" | cut -d',' -f2)
                    end_time=$(printf '%s' "$line" | cut -d',' -f3)

                    # Convert ASS time to seconds with error handling
                    local start_sec end_sec duration
                    start_sec=$(ass_time_to_seconds "$start_time" 2>/dev/null || echo "0")
                    end_sec=$(ass_time_to_seconds "$end_time" 2>/dev/null || echo "0")

                    # Only process if both conversions succeeded
                    if [[ "$start_sec" != "0" || "$start_time" == "0:00:00.00" ]] && \
                       [[ "$end_sec" != "0" || "$end_time" == "0:00:00.00" ]]; then

                        duration=$(bc_calc "$end_sec - $start_sec" 2>/dev/null || echo "0")

                        if [[ "$duration" != "0" ]] && [[ "$duration" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                            total_duration=$(bc_calc "$total_duration + $duration" 2>/dev/null || echo "$total_duration")

                            if bc_compare "$duration < $MIN_SUBTITLE_DURATION" 2>/dev/null; then
                                ((very_short_count++))
                            fi
                        fi
                    fi

                    # Check for empty text content
                    local text_content
                    text_content=$(printf '%s' "$line" | cut -d',' -f10-)
                    if [[ -z "${text_content// /}" ]]; then
                        ((empty_count++))
                    fi
                fi
            done < "$temp_sub"
        fi

        # Analyze results
        if [[ $subtitle_count -eq 0 ]]; then
            issues+=("no_subtitles")
        else
            # Check subtitle rate (subtitles per second) with error handling
            local subtitle_rate
            subtitle_rate=$(bc_calc "scale=3; $subtitle_count / $video_duration" 2>/dev/null || echo "0")

            if [[ "$subtitle_rate" != "0" ]] && [[ "$subtitle_rate" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                if bc_compare "$subtitle_rate < $MIN_SUBTITLE_RATE" 2>/dev/null; then
                    issues+=("low_subtitle_rate:$subtitle_rate")
                fi
            fi

            # Check for too many empty subtitles
            if [[ $subtitle_count -gt 0 ]]; then
                local empty_ratio
                empty_ratio=$(bc_calc "scale=3; $empty_count / $subtitle_count" 2>/dev/null || echo "0")

                if [[ $empty_count -gt $MAX_EMPTY_SUBS ]] && [[ "$empty_ratio" != "0" ]] && [[ "$empty_ratio" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                    if bc_compare "$empty_ratio > 0.3" 2>/dev/null; then
                        issues+=("too_many_empty:$empty_count/$subtitle_count")
                    fi
                fi

                # Check for too many very short subtitles
                local short_ratio
                short_ratio=$(bc_calc "scale=3; $very_short_count / $subtitle_count" 2>/dev/null || echo "0")

                if [[ "$short_ratio" != "0" ]] && [[ "$short_ratio" =~ ^[0-9]*\.?[0-9]+$ ]]; then
                    if bc_compare "$short_ratio > 0.5" 2>/dev/null; then
                        issues+=("too_many_short:$very_short_count/$subtitle_count")
                    fi
                fi
            fi
        fi
    fi

    # Cleanup
    rm -f "$temp_sub" "$temp_ass"

    # Return issues (only to stdout)
    if [[ ${#issues[@]} -gt 0 ]]; then
        printf '%s\n' "${issues[@]}"
    fi
}

# Function to analyze all subtitle streams
analyze_subtitles() {
    local file="$1"
    local info_json="$2"
    local problematic_subs=()

    # Get video duration
    local video_duration
    video_duration=$(printf '%s' "$info_json" | jq -r '.format.duration // empty' 2>/dev/null)
    if [[ -z "$video_duration" ]] || [[ "$video_duration" == "null" ]]; then
        return 0
    fi

    # Get subtitle stream indices
    local sub_indices
    sub_indices=$(printf '%s' "$info_json" | jq -r '.streams[] | select(.codec_type=="subtitle") | .index' 2>/dev/null)

    if [[ -z "$sub_indices" ]]; then
        return 0
    fi

    while IFS= read -r index; do
        [[ -z "$index" ]] && continue

        # Validate that index is numeric
        if [[ ! "$index" =~ ^[0-9]+$ ]]; then
            continue
        fi

        local issues
        # Don't let subtitle analysis failure stop the whole process
        if issues=$(analyze_subtitle_content "$file" "$index" "$video_duration" 2>/dev/null); then
            if [[ -n "$issues" ]]; then
                problematic_subs+=("$index")
            fi
        fi
    done <<< "$sub_indices"

    # Return problematic subtitle indices
    printf '%s\n' "${problematic_subs[@]}"
}

# Function to build ffmpeg command for subtitle removal
build_ffmpeg_command() {
    local input_file="$1"
    local output_file="$2"
    local problematic_subs="$3"

    local cmd=(ffmpeg -v warning -i "$input_file")

    # Build map commands to exclude problematic subtitle streams
    local info_json
    if ! info_json=$(get_video_info "$input_file"); then
        return 1
    fi

    # Map all non-problematic streams
    local stream_count
    stream_count=$(printf '%s' "$info_json" | jq -r '.streams | length' 2>/dev/null)

    for ((i=0; i<stream_count; i++)); do
        local stream_type
        stream_type=$(printf '%s' "$info_json" | jq -r ".streams[$i].codec_type" 2>/dev/null)

        if [[ "$stream_type" == "subtitle" ]]; then
            # Check if this subtitle stream is problematic
            local is_problematic=false
            while IFS= read -r prob_index; do
                [[ -z "$prob_index" ]] && continue
                if [[ "$i" -eq "$prob_index" ]]; then
                    is_problematic=true
                    break
                fi
            done <<< "$problematic_subs"

            if [[ "$is_problematic" == "false" ]]; then
                cmd+=(-map "0:$i")
            fi
        else
            cmd+=(-map "0:$i")
        fi
    done

    cmd+=(-c copy -f matroska "$output_file")

    printf '%s\0' "${cmd[@]}"
}

# Function to process a single MKV file
process_mkv_file() {
    local file="$1"
    local basename filename extension output_file

    basename=$(basename "$file")
    filename="${basename%.*}"
    extension="${basename##*.}"
    output_file="${file%.*}${OUTPUT_SUFFIX}.${extension}"

    log "Processing: $file"

    # Check if output file already exists
    if [[ -f "$output_file" ]]; then
        warning "Output file already exists, skipping: $output_file"
        return 0
    fi

    # Get video information
    local info_json
    if ! info_json=$(get_video_info "$file"); then
        error "Failed to get video info for: $file"
        return 1
    fi

    # Analyze subtitles
    local problematic_subs
    problematic_subs=$(analyze_subtitles "$file" "$info_json")

    # Decide if processing is needed
    if [[ -z "$problematic_subs" ]]; then
        success "No problematic subtitles found in: $file (no output file created)"
        return 0
    fi

    log "Problematic subtitles found in $file, creating cleaned version..."
    log "Problematic subtitle streams: $problematic_subs"

    # Build and execute ffmpeg command
    local ffmpeg_cmd
    if ! readarray -d '' ffmpeg_cmd < <(build_ffmpeg_command "$file" "$output_file" "$problematic_subs" 2>/dev/null); then
        error "Failed to build ffmpeg command for: $file"
        return 1
    fi

    log "Creating cleaned file: $(basename "$output_file")"

    # Execute ffmpeg command with error handling
    if "${ffmpeg_cmd[@]}" >/dev/null 2>&1; then
        # Verify the output file
        if [[ -f "$output_file" ]]; then
            success "Successfully created cleaned file: $output_file"
            return 0
        else
            error "Output file not created: $output_file"
            return 1
        fi
    else
        error "FFmpeg processing failed for: $file"
        # Clean up partial file if it exists
        [[ -f "$output_file" ]] && rm -f "$output_file"
        return 1
    fi
}

# Function to find and process all MKV files
process_all_mkv_files() {
    local start_dir="${1:-.}"
    local processed=0 failed=0 skipped=0

    log "Starting recursive search for MKV files in: $start_dir"

    # Use find with proper handling of spaces and special characters
    while IFS= read -r -d '' file; do
        # Skip files that already have the output suffix
        if [[ "$file" == *"$OUTPUT_SUFFIX.mkv" ]]; then
            ((skipped++))
            continue
        fi

        # Process the file - don't let individual file failures stop processing
        if process_mkv_file "$file"; then
            ((processed++))
        else
            ((failed++))
        fi
        echo "----------------------------------------"
    done < <(find "$start_dir" -type f -name "*.mkv" -print0 2>/dev/null)

    log "Processing complete. Processed: $processed, Failed: $failed, Skipped: $skipped"
    return 0
}

# Function to cleanup on exit
cleanup() {
    rm -f /tmp/subtitle_*_$$.srt /tmp/subtitle_*_$$.ass 2>/dev/null || true
}

# Main function
main() {
    local start_dir="${1:-.}"

    # Set up cleanup trap
    trap cleanup EXIT

    # Check dependencies
    check_dependencies

    # Check if jq is available for JSON parsing
    if ! command -v jq &> /dev/null; then
        error "jq is not installed. Please install jq for JSON parsing."
        exit 1
    fi

    # Check if bc is available for calculations
    if ! command -v bc &> /dev/null; then
        error "bc is not installed. Please install bc for mathematical calculations."
        exit 1
    fi

    # Validate start directory
    if [[ ! -d "$start_dir" ]]; then
        error "Directory does not exist: $start_dir"
        exit 1
    fi

    log "Starting MKV subtitle cleanup process"
    log "Configuration:"
    log "  - Minimum subtitle duration: ${MIN_SUBTITLE_DURATION}s"
    log "  - Minimum subtitle rate: ${MIN_SUBTITLE_RATE} entries/second"
    log "  - Maximum empty subtitles: $MAX_EMPTY_SUBS"
    log "  - Output suffix: $OUTPUT_SUFFIX"

    # Process all MKV files
    process_all_mkv_files "$start_dir"

    success "MKV subtitle cleanup process completed"
}

# Script usage
usage() {
    cat << EOF
Usage: $0 [directory]

This script recursively finds all *.mkv files and processes them to remove erroneous subtitles.

Options:
  directory    Starting directory for recursive search (default: current directory)

The script will detect and remove subtitle streams with:
- Very short display duration (< ${MIN_SUBTITLE_DURATION}s per subtitle)
- Low subtitle rate (< ${MIN_SUBTITLE_RATE} entries/second)
- Too many empty subtitle entries
- Empty subtitle files

When problematic subtitles are found, a new file will be created with the suffix ${OUTPUT_SUFFIX}.mkv
The original file will be left untouched.

Requirements:
- ffmpeg
- ffprobe
- jq (for JSON parsing)
- bc (for mathematical calculations)

EOF
}

# Check for help flag
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

# Run main function
main "$@"