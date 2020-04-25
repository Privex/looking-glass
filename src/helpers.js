
export function trim_path(path, start_asns = 3, end_asns = 3) {
    if (path.length > (start_asns + end_asns) - 1) {
        return `${path.slice(0, start_asns).join(', ')} ... ${path.slice(-end_asns)}`
    }
    return path.join(', ')
}

export function trim_words(name, max_words = 6) {
    let nsplit = name.split(' ');
    nsplit = (nsplit.length > max_words) ? nsplit.splice(0, max_words) : nsplit;
    return nsplit.join(' ')
}
export function trim_name(name, max_length = 40, max_words = 6) {
    if (name.length > max_length) {
        let nname = trim_words(name, max_words);
        if (nname > max_length) {
            nname = trim_words(name, max_words - 1);
            nname = (nname.length > max_length) ? nname.substr(0, max_length) : nname;
        }
        return nname + '...'
    }
    return name;
}
