// Resolves the Lambda deploy architecture to match whatever machine is
// running `serverless deploy` (e.g. compiled dependencies like pymongo get
// installed for that same architecture).
module.exports.get = () => (process.arch === 'arm64' ? 'arm64' : 'x86_64')
