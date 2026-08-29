module.exports.get = () => (process.arch === 'arm64' ? 'arm64' : 'x86_64')
