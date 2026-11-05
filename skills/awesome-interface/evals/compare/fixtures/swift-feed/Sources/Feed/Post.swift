import Foundation

final class Post: Identifiable {
    let id: UUID
    var author: String
    var text: String
    var imageURL: URL?
    var likeCount: Int

    init(id: UUID = UUID(), author: String, text: String, imageURL: URL?, likeCount: Int) {
        self.id = id
        self.author = author
        self.text = text
        self.imageURL = imageURL
        self.likeCount = likeCount
    }
}
