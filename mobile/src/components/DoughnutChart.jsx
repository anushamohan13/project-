import React from 'react';
import { Text, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';
import { palette } from '../theme/tokens';

const colors = [palette.blue, palette.green, palette.orange, palette.purple, palette.teal, palette.gray, palette.red];

export default function DoughnutChart({ allocations = [], currency = 'SGD' }) {
  const size = 240;
  const strokeWidth = 34;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const visible = allocations.filter((item) => !item.informational && Number(item.amount) > 0);
  const total = visible.reduce((sum, item) => sum + Number(item.amount), 0);
  let offset = 0;

  return (
    <View accessibilityLabel={`Budget chart. Total ${currency} ${total.toFixed(2)}`}>
      <View style={{ alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={size} height={size} style={{ transform: [{ rotate: '-90deg' }] }}>
          <Circle cx={size / 2} cy={size / 2} r={radius} stroke="#E5E5EA" strokeWidth={strokeWidth} fill="none" />
          {visible.map((item, index) => {
            const length = total ? (Number(item.amount) / total) * circumference : 0;
            const segment = (
              <Circle
                key={item.category}
                cx={size / 2}
                cy={size / 2}
                r={radius}
                stroke={colors[index % colors.length]}
                strokeWidth={strokeWidth}
                fill="none"
                strokeDasharray={`${length} ${circumference - length}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
              />
            );
            offset += length;
            return segment;
          })}
        </Svg>
        <View style={{ position: 'absolute', alignItems: 'center' }}>
          <Text style={{ fontSize: 14 }}>Available</Text>
          <Text style={{ fontSize: 28, fontWeight: '800' }}>{currency} {total.toFixed(0)}</Text>
        </View>
      </View>
      <View style={{ marginTop: 14 }}>
        {visible.map((item, index) => (
          <View key={item.category} style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 8 }}>
            <View style={{ width: 12, height: 12, borderRadius: 6, backgroundColor: colors[index % colors.length], marginRight: 8 }} />
            <Text style={{ flex: 1 }}>{item.category}</Text>
            <Text style={{ fontWeight: '600' }}>{currency} {Number(item.amount).toFixed(2)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}
