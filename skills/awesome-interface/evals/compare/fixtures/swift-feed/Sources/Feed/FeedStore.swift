import Foundation
import Observation

@Observable
final class FeedStore {
    var posts: [Post] = []
    var images: [UUID: Data] = [:]
    var isLoading = false
    var errorMessage: String?

    private let endpoint = URL(string: "https://api.example.com/feed")!

    func refresh() {
        isLoading = true
        Task.detached {
            do {
                let (data, _) = try await URLSession.shared.data(from: self.endpoint)
                let decoded = try JSONDecoder().decode([PostDTO].self, from: data)
                self.posts = decoded.map(\.post)
                self.isLoading = false
                await self.loadImages()
            } catch {
                DispatchQueue.main.async {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                }
            }
        }
    }

    func loadImages() async {
        await withTaskGroup(of: Void.self) { group in
            for post in posts {
                guard let url = post.imageURL else { continue }
                group.addTask {
                    if let data = try? await ImageCache.shared.image(for: url) {
                        self.images[post.id] = data
                    }
                }
            }
        }
    }

    func like(_ post: Post) {
        post.likeCount += 1
        Task.detached {
            var request = URLRequest(url: URL(string: "https://api.example.com/posts/\(post.id)/like")!)
            request.httpMethod = "POST"
            _ = try? await URLSession.shared.data(for: request)
        }
    }
}

struct PostDTO: Decodable {
    let id: UUID
    let author: String
    let text: String
    let imageURL: URL?
    let likeCount: Int

    var post: Post {
        Post(id: id, author: author, text: text, imageURL: imageURL, likeCount: likeCount)
    }
}
