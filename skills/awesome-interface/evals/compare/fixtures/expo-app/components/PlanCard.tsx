import { Pressable, StyleSheet, Text, View } from "react-native";

type Plan = { id: string; name: string; price: string; perks: string[] };

export function PlanCard({ plan, selected, onPress }: { plan: Plan; selected: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="radio" accessibilityState={{ selected }}>
      <View style={[styles.card, selected && styles.selected]}>
        <Text style={styles.name}>{plan.name}</Text>
        <Text style={styles.price}>{plan.price}</Text>
        {plan.perks.map((perk) => (
          <Text key={perk} style={styles.perk}>· {perk}</Text>
        ))}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { padding: 16, borderRadius: 14, borderWidth: 1, borderColor: "#e2e5e9", backgroundColor: "#fff" },
  selected: { borderColor: "#2d62e0", borderWidth: 2 },
  name: { fontSize: 17, fontWeight: "600" },
  price: { fontSize: 15, marginTop: 4, color: "#2d62e0" },
  perk: { fontSize: 14, marginTop: 2, color: "#5f6670" },
});
