
export function trim_path(path, start_asns = 3, end_asns = 3) {
    if (path.length > (start_asns + end_asns) - 1) {
        return `${path.slice(0, start_asns).join(', ')} ... ${path.slice(-end_asns)}`
    }
    return path.join(', ')
}

