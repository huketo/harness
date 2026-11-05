import { useState } from "react";
import { ScrollView, StyleSheet, Text, View, Pressable } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { PlanCard } from "../components/PlanCard";
import { FilterSheet } from "../components/FilterSheet";

const PLANS = [
  { id: "basic", name: "베이직", price: "월 9,900원", perks: ["기기 1대", "광고 없음"] },
  { id: "family", name: "패밀리", price: "월 16,900원", perks: ["기기 4대", "프로필 6개"] },
  { id: "pro", name: "프로", price: "월 24,900원", perks: ["4K 화질", "오프라인 저장"] },
];

export default function PlansScreen() {
  const [selected, setSelected] = useState("family");
  const [filterOpen, setFilterOpen] = useState(false);

  return (
    <SafeAreaView style={styles.screen}>
      <View style={styles.header}>
        <Text style={styles.title}>요금제 선택</Text>
        <Pressable onPress={() => setFilterOpen(true)} style={styles.filterButton}>
          <Text style={styles.filterText}>필터</Text>
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={styles.list}>
        {PLANS.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            selected={selected === plan.id}
            onPress={() => setSelected(plan.id)}
          />
        ))}
      </ScrollView>
      <FilterSheet open={filterOpen} onClose={() => setFilterOpen(false)} />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: "#fff" },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16 },
  title: { fontSize: 22, fontWeight: "700" },
  filterButton: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: "#e2e5e9" },
  filterText: { fontSize: 15 },
  list: { padding: 16, gap: 12 },
});
