import React, { useState } from 'react';
import { Alert, ScrollView, Text, View } from 'react-native';

import FormField from '../components/FormField';
import PrimaryButton from '../components/PrimaryButton';
import DoughnutChart from '../components/DoughnutChart';
import AllocationEditor from '../components/AllocationEditor';
import { api } from '../api/client';
import { spacing } from '../theme/tokens';
import { syncWidgetSnapshot } from '../services/widgetSnapshot';

function isoDate(offset = 0) {
  const value = new Date();
  value.setDate(value.getDate() + offset);
  return value.toISOString().slice(0, 10);
}

export default function PlannerScreen() {
  const [salary, setSalary] = useState('1500');
  const [activityName, setActivityName] = useState('Groceries');
  const [activityCost, setActivityCost] = useState('180');
  const [wishlistContribution, setWishlistContribution] = useState('50');
  const [result, setResult] = useState(null);
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(false);

  async function calculate() {
    setLoading(true);
    try {
      const incomes = await api.listIncome();
      if (!incomes.length) {
        const weekday = new Date().getDay() === 0 ? 6 : new Date().getDay() - 1;
        await api.createIncome({
          name: 'Main Salary', amount: salary, currency: 'SGD', frequency: 'weekly',
          payment_weekday: weekday, payment_day_of_month: null, next_payment_date: isoDate(0),
          is_active: true, notes: null,
        });
      }
      await api.createActivity({
        name: activityName, category: activityName, activity_date: isoDate(1), city: 'Singapore',
        people_count: 1, estimated_cost: activityCost, actual_cost: null, currency: 'SGD',
        manually_entered: true, recurring: false, priority: 'essential', completed: false, notes: null,
      });
      const calculated = await api.calculateBudget({
        period_start: isoDate(0), period_end: isoDate(6), wishlist_contribution: wishlistContribution,
      });
      setResult(calculated);
      setAllocations(calculated.allocations.map(({ category, amount, locked, informational }) => ({ category, amount, locked, informational })));
    } catch (error) { Alert.alert('Calculation failed', error.message); }
    finally { setLoading(false); }
  }

  async function confirm() {
    try {
      const fundedTotal = allocations
        .filter((item) => !item.informational)
        .reduce((sum, item) => sum + Number(item.amount), 0);
      if (Math.abs(fundedTotal - Number(result.total_available)) > 0.009) {
        Alert.alert('Allocation mismatch', 'Funded categories must exactly equal the available total.');
        return;
      }
      await api.confirmBudget({
        period_start: result.period_start,
        period_end: result.period_end,
        currency: result.currency,
        total_available: result.total_available,
        allocations,
      });
      const snapshot = await api.widgetSnapshot();
      await syncWidgetSnapshot(snapshot);
      Alert.alert('Plan confirmed', 'A new immutable plan version and widget snapshot were created.');
    } catch (error) { Alert.alert('Could not confirm plan', error.message); }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg }} keyboardShouldPersistTaps="handled">
      <Text style={{ fontSize: 26, fontWeight: '800', marginBottom: spacing.lg }}>Build this week’s plan</Text>
      <FormField label="Weekly salary" value={salary} onChangeText={setSalary} keyboardType="decimal-pad" />
      <FormField label="Activity" value={activityName} onChangeText={setActivityName} />
      <FormField label="Estimated activity cost" value={activityCost} onChangeText={setActivityCost} keyboardType="decimal-pad" />
      <FormField label="Smart Wishlist contribution" value={wishlistContribution} onChangeText={setWishlistContribution} keyboardType="decimal-pad" />
      <PrimaryButton title="Calculate recommended plan" onPress={calculate} loading={loading} />
      {result && (
        <View style={{ marginTop: spacing.xl }}>
          <DoughnutChart allocations={allocations} currency={result.currency} />
          <AllocationEditor allocations={allocations} totalAvailable={result.total_available} currency={result.currency} onChange={setAllocations} />
          {result.warnings.map((warning) => <Text key={warning} style={{ color: '#FF9F0A', marginVertical: 4 }}>{warning}</Text>)}
          <PrimaryButton title="Confirm adjusted plan" onPress={confirm} />
        </View>
      )}
    </ScrollView>
  );
}
