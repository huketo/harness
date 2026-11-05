import { useEffect, useRef, useState } from "react";
import { Animated, Dimensions, PanResponder, Pressable, StyleSheet, Text, View } from "react-native";

const SCREEN_HEIGHT = Dimensions.get("window").height;
const SHEET_HEIGHT = 360;

export function FilterSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const height = useRef(new Animated.Value(0)).current;
  const [dragY, setDragY] = useState(0);

  useEffect(() => {
    Animated.timing(height, {
      toValue: open ? SHEET_HEIGHT : 0,
      duration: 400,
      useNativeDriver: false,
    }).start();
  }, [open, height]);

  const pan = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 4,
      onPanResponderMove: (_, g) => setDragY(Math.max(0, g.dy)),
      onPanResponderRelease: (_, g) => {
        setDragY(0);
        if (g.dy > SHEET_HEIGHT / 2) onClose();
      },
    })
  ).current;

  return (
    <View pointerEvents={open ? "auto" : "none"} style={StyleSheet.absoluteFill}>
      {open && <Pressable style={styles.scrim} onPress={onClose} />}
      <Animated.View
        style={[styles.sheet, { height, top: SCREEN_HEIGHT - SHEET_HEIGHT + dragY }]}
        {...pan.panHandlers}
      >
        <View style={styles.handle} />
        <Text style={styles.title}>필터</Text>
        <Text style={styles.option}>가격 낮은 순</Text>
        <Text style={styles.option}>인기 순</Text>
        <Text style={styles.option}>4K 지원만</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  scrim: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(0,0,0,0.4)" },
  sheet: {
    position: "absolute",
    left: 0,
    right: 0,
    overflow: "hidden",
    backgroundColor: "#fff",
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingHorizontal: 16,
  },
  handle: { alignSelf: "center", width: 40, height: 5, borderRadius: 3, backgroundColor: "#d6d9de", marginVertical: 10 },
  title: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
  option: { fontSize: 16, paddingVertical: 12 },
});
