import React, { useMemo } from 'react';
import { Switch, Text, View } from 'react-native';
import Slider from '@react-native-community/slider';

import { spacing } from '../theme/tokens';

function roundMoney(value) {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

export default function AllocationEditor({ allocations, totalAvailable, currency, onChange }) {
  const max = Math.max(Number(totalAvailable), 1);
  const fundedTotal = useMemo(
    () => allocations.filter((item) => !item.informational).reduce((sum, item) => sum + Number(item.amount), 0),
    [allocations],
  );

  function updateLock(index, locked) {
    const next = allocations.map((item, itemIndex) => (itemIndex === index ? { ...item, locked } : item));
    onChange(next);
  }

  function updateAmount(index, rawValue) {
    const selected = allocations[index];
    if (selected.informational || selected.category === 'Remaining available balance') return;
    const remainingIndex = allocations.findIndex((item) => item.category === 'Remaining available balance');
    if (remainingIndex < 0) return;
    const oldAmount = Number(selected.amount);
    const currentRemaining = Number(allocations[remainingIndex].amount);
    const requested = roundMoney(rawValue);
    const maximumAllowed = roundMoney(oldAmount + currentRemaining);
    const nextAmount = Math.max(0, Math.min(requested, maximumAllowed));
    const delta = roundMoney(nextAmount - oldAmount);
    const next = allocations.map((item, itemIndex) => {
      if (itemIndex === index) return { ...item, amount: nextAmount.toFixed(2) };
      if (itemIndex === remainingIndex) return { ...item, amount: roundMoney(currentRemaining - delta).toFixed(2) };
      return item;
    });
    onChange(next);
  }

  return (
    <View style={{ marginTop: spacing.lg }}>
      <Text style={{ fontSize: 20, fontWeight: '800', marginBottom: spacing.sm }}>Adjust allocations</Text>
      <Text style={{ color: '#666', marginBottom: spacing.md }}>
        Funded total: {currency} {fundedTotal.toFixed(2)} / {currency} {Number(totalAvailable).toFixed(2)}
      </Text>
      {allocations.map((item, index) => (
        <View key={item.category} style={{ paddingVertical: spacing.sm, borderBottomWidth: 0.5, borderBottomColor: 'rgba(142,142,147,0.35)' }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View style={{ flex: 1, paddingRight: spacing.sm }}>
              <Text style={{ fontWeight: '700' }}>{item.category}</Text>
              <Text style={{ color: '#666' }}>{currency} {Number(item.amount).toFixed(2)}</Text>
            </View>
            {!item.informational && item.category !== 'Remaining available balance' && (
              <View style={{ alignItems: 'center' }}>
                <Text style={{ fontSize: 11, color: '#777' }}>Lock</Text>
                <Switch value={Boolean(item.locked)} onValueChange={(value) => updateLock(index, value)} />
              </View>
            )}
          </View>
          {!item.informational && item.category !== 'Remaining available balance' && (
            <Slider
              minimumValue={0}
              maximumValue={max}
              step={1}
              value={Number(item.amount)}
              disabled={Boolean(item.locked)}
              onValueChange={(value) => updateAmount(index, value)}
              accessibilityLabel={`Adjust ${item.category}`}
            />
          )}
        </View>
      ))}
    </View>
  );
}
