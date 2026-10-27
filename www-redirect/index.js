// Bound only to www.makecv.org: permanently redirect every request to the apex,
// keeping path and query, so search engines see a single canonical host.
const worker = {
  fetch(request) {
    const url = new URL(request.url)
    url.hostname = 'makecv.org'
    url.protocol = 'https:'
    url.port = ''
    return Response.redirect(url.toString(), 301)
  },
}

export default worker
