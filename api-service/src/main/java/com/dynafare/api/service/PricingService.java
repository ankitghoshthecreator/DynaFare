package com.dynafare.api.service;

import com.dynafare.api.domain.Quote;
import com.dynafare.api.domain.User;
import com.dynafare.api.dto.QuoteRequest;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class PricingService {

    private final RestTemplate restTemplate;

    @Value("${ml.service.url}")
    private String mlServiceUrl;

    public record MlPredictionResponse(
            Double price,
            Double eta_minutes,
            Double surge_multiplier,
            Double confidence,
            String source
    ) {}

    @CircuitBreaker(name = "mlService", fallbackMethod = "fallbackPricing")
    public Quote generateQuote(QuoteRequest request, User rider) {
        log.info("Requesting live ML pricing for rider {}", rider.getId());

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        Map<String, Object> payload = new HashMap<>();
        payload.put("pickup_lat", request.getPickupLat());
        payload.put("pickup_lon", request.getPickupLon());
        payload.put("dropoff_lat", request.getDropoffLat());
        payload.put("dropoff_lon", request.getDropoffLon());
        payload.put("rider_id", rider.getId().toString());

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(payload, headers);

        MlPredictionResponse response = restTemplate.postForObject(
                mlServiceUrl + "/predict",
                entity,
                MlPredictionResponse.class
        );

        if (response == null) {
            throw new RuntimeException("ML service returned null response");
        }

        return Quote.builder()
                .rider(rider)
                .pickupLat(request.getPickupLat())
                .pickupLon(request.getPickupLon())
                .dropoffLat(request.getDropoffLat())
                .dropoffLon(request.getDropoffLon())
                .predictedPrice(BigDecimal.valueOf(response.price()))
                .predictedEta(BigDecimal.valueOf(response.eta_minutes()))
                .surgeMultiplier(BigDecimal.valueOf(response.surge_multiplier()))
                .confidence(BigDecimal.valueOf(response.confidence()))
                .build();
    }

    /**
     * Fallback method called when the ML service is down or times out.
     */
    public Quote fallbackPricing(QuoteRequest request, User rider, Throwable t) {
        log.warn("ML Service unavailable, falling back to flat-rate pricing for rider {}. Error: {}", rider.getId(), t.getMessage());

        double distanceKm = haversineKm(request.getPickupLat(), request.getPickupLon(),
                request.getDropoffLat(), request.getDropoffLon());
        
        // Base rate: $1.50 per km + $2.00 base fare (or equivalent INR: 12 Rs/km)
        double baseRatePerKm = 12.0;
        double baseMinutesPerKm = 3.5;
        
        double price = Math.max(baseRatePerKm * distanceKm, 30.0);
        double eta = Math.max(baseMinutesPerKm * distanceKm, 5.0);
        
        return Quote.builder()
                .rider(rider)
                .pickupLat(request.getPickupLat())
                .pickupLon(request.getPickupLon())
                .dropoffLat(request.getDropoffLat())
                .dropoffLon(request.getDropoffLon())
                .predictedPrice(BigDecimal.valueOf(price))
                .predictedEta(BigDecimal.valueOf(eta))
                .surgeMultiplier(BigDecimal.ONE)
                .confidence(BigDecimal.valueOf(0.5)) // Low confidence since it's a static fallback
                .build();
    }

    /**
     * Haversine distance formula used for the fallback calculation.
     */
    private double haversineKm(double lat1, double lon1, double lat2, double lon2) {
        final int R = 6371; // Radius of the earth in km
        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);
        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                        Math.sin(dLon / 2) * Math.sin(dLon / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c; // Distance in km
    }
}
