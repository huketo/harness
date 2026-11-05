import Foundation

final class ImageCache: @unchecked Sendable {
    static let shared = ImageCache()

    private var storage: [URL: Data] = [:]

    func image(for url: URL) async throws -> Data {
        if let cached = storage[url] {
            return cached
        }
        let (data, _) = try await URLSession.shared.data(from: url)
        storage[url] = data
        return data
    }
}
