"use client";

import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import React, { useEffect, useRef } from 'react';

interface StockChartProps {
  data: any[];
  maPeriods?: number[];
  colors?: {
    backgroundColor?: string;
    lineColor?: string;
    textColor?: string;
    areaTopColor?: string;
    areaBottomColor?: string;
  };
}

const MA_COLORS = ['#2962FF', '#FF6D00', '#4CAF50', '#9C27B0', '#E91E63'];

export const StockChart = (props: StockChartProps) => {
  const {
    data,
    maPeriods = [],
    colors: {
      backgroundColor = 'white',
      lineColor = '#2962FF',
      textColor = 'black',
    } = {},
  } = props;

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maSeriesRefs = useRef<ISeriesApi<"Line">[]>([]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const handleResize = () => {
      chartRef.current?.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: backgroundColor },
        textColor,
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      },
    });
    chartRef.current = chart;

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#ef5350',
        downColor: '#26a69a',
        borderVisible: false,
        wickUpColor: '#ef5350',
        wickDownColor: '#26a69a',
    });
    candlestickSeriesRef.current = candlestickSeries;

    const volumeSeries = chart.addSeries(HistogramSeries, {
        color: '#26a69a',
        priceFormat: {
            type: 'volume',
        },
        priceScaleId: '', // set as an overlay
    });
    volumeSeriesRef.current = volumeSeries;
    
    volumeSeries.priceScale().applyOptions({
        scaleMargins: {
            top: 0.8, // highest point of the series will be 80% from top
            bottom: 0,
        },
    });

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [backgroundColor, textColor]);

  useEffect(() => {
    if (!chartRef.current || !candlestickSeriesRef.current || !data || data.length === 0) return;

    // Clear old MA series
    maSeriesRefs.current.forEach(s => chartRef.current?.removeSeries(s));
    maSeriesRefs.current = [];

    // Set Candlestick data
    candlestickSeriesRef.current.setData(data);
    
    // Set Volume data
    const volumeData = data.map(d => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open ? '#ef5350' : '#26a69a'
    }));
    volumeSeriesRef.current?.setData(volumeData);

    // Calculate and Add MA series
    maPeriods.forEach((period, index) => {
        if (data.length < period) return;

        const maData = [];
        for (let i = period - 1; i < data.length; i++) {
            const sum = data.slice(i - period + 1, i + 1).reduce((acc, curr) => acc + curr.close, 0);
            maData.push({
                time: data[i].time,
                value: sum / period,
            });
        }

        if (maData.length > 0) {
            const maSeries = chartRef.current!.addSeries(LineSeries, {
                color: MA_COLORS[index % MA_COLORS.length],
                lineWidth: 1,
                title: `MA${period}`,
            });
            maSeries.setData(maData);
            maSeriesRefs.current.push(maSeries);
        }
    });
    
    chartRef.current?.timeScale().fitContent();
  }, [data, maPeriods]);

  return (
    <div
      ref={chartContainerRef}
      className="w-full h-[400px]"
    />
  );
};
