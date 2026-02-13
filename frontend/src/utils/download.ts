export async function saveBlobAs(blob: Blob, filename: string): Promise<void> {
  const url = URL.createObjectURL(blob)
  try {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function blobToText(blob: Blob): Promise<string> {
  return await blob.text()
}

/**
 * Extract filename from an absolute path (Windows or Posix)
 */
export function extractFilename(path: string): string {
  // Handle Windows paths
  const winParts = path.split('\\')
  if (winParts.length > 1) {
    return winParts[winParts.length - 1]
  }
  // Handle Posix paths
  const parts = path.split('/')
  return parts[parts.length - 1]
}

