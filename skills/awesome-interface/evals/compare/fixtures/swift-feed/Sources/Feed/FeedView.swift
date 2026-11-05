#if canImport(SwiftUI)
import SwiftUI

struct FeedView: View {
    @State private var store = FeedStore()

    var body: some View {
        NavigationStack {
            List(store.posts) { post in
                VStack(alignment: .leading, spacing: 8) {
                    Text(post.author).font(.headline)
                    Text(post.text).font(.body)
                    if let data = store.images[post.id] {
                        ImageView(data: data)
                            .frame(maxWidth: .infinity, minHeight: 180)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    Button {
                        store.like(post)
                    } label: {
                        Label("\(post.likeCount)", systemImage: "heart")
                    }
                    .buttonStyle(.borderless)
                }
                .padding(.vertical, 6)
            }
            .overlay {
                if store.isLoading { ProgressView() }
            }
            .navigationTitle("피드")
            .refreshable { store.refresh() }
            .task { store.refresh() }
        }
    }
}

private struct ImageView: View {
    let data: Data
    var body: some View {
        #if canImport(UIKit)
        if let image = UIImage(data: data) {
            Image(uiImage: image).resizable().scaledToFill()
        }
        #else
        Color.gray.opacity(0.2)
        #endif
    }
}
#endif
