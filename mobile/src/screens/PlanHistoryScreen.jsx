import React, { useEffect, useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';

import { api } from '../api/client';
import PrimaryButton from '../components/PrimaryButton';
import { spacing } from '../theme/tokens';

export default function PlanHistoryScreen() {
  const [plans, setPlans] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const history = await api.budgetHistory();
      setPlans(history);
      if (history.length >= 2) setComparison(await api.compareBudgets(history[1].id, history[0].id));
    } catch (error) { Alert.alert('Could not load plan history', error.message); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
      <PrimaryButton title="Refresh plan history" onPress={load} loading={loading} />
      {comparison && (
        <View style={{ marginTop: spacing.lg, padding: spacing.md, borderRadius: 18, backgroundColor: 'rgba(142,142,147,0.12)' }}>
          <Text style={{ fontSize: 20, fontWeight: '800' }}>Version {comparison.left_plan.version} → {comparison.right_plan.version}</Text>
          <Text>Remaining balance change: {comparison.right_plan.currency} {Number(comparison.remaining_difference).toFixed(2)}</Text>
          {comparison.allocation_changes.filter((item) => Math.abs(Number(item.difference)) > 0.001).map((item) => (
            <Text key={item.category} style={{ marginTop: 6 }}>{item.category}: {Number(item.difference) >= 0 ? '+' : ''}{Number(item.difference).toFixed(2)}</Text>
          ))}
        </View>
      )}
      <Text style={{ fontSize: 22, fontWeight: '800', marginTop: spacing.xl, marginBottom: spacing.md }}>Immutable versions</Text>
      {plans.map((plan) => (
        <View key={plan.id} style={{ padding: spacing.md, borderRadius: 16, backgroundColor: 'rgba(142,142,147,0.12)', marginBottom: spacing.md }}>
          <Text style={{ fontWeight: '800' }}>Version {plan.version} · {plan.source}</Text>
          <Text>{plan.period_start} to {plan.period_end}</Text>
          <Text>Remaining: {plan.currency} {Number(plan.remaining_balance).toFixed(2)}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
