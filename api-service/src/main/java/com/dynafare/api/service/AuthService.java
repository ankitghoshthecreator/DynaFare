package com.dynafare.api.service;

import com.dynafare.api.domain.Driver;
import com.dynafare.api.domain.DriverStatus;
import com.dynafare.api.domain.Role;
import com.dynafare.api.domain.User;
import com.dynafare.api.dto.AuthRequest;
import com.dynafare.api.dto.AuthResponse;
import com.dynafare.api.dto.RegisterRequest;
import com.dynafare.api.repository.DriverRepository;
import com.dynafare.api.repository.UserRepository;
import com.dynafare.api.security.JwtUtil;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final DriverRepository driverRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;
    private final AuthenticationManager authenticationManager;

    @Transactional
    public AuthResponse register(RegisterRequest request) {
        if (userRepository.findByEmail(request.getEmail()).isPresent()) {
            throw new IllegalArgumentException("User with email already exists");
        }

        var user = User.builder()
                .email(request.getEmail())
                .passwordHash(passwordEncoder.encode(request.getPassword()))
                .role(request.getRole() != null ? request.getRole() : Role.RIDER)
                .build();
        
        userRepository.save(user);

        if (user.getRole() == Role.DRIVER) {
            var driver = Driver.builder()
                    .user(user)
                    .status(DriverStatus.OFFLINE)
                    .build();
            driverRepository.save(driver);
        }

        var jwtToken = jwtUtil.generateToken(user);
        return AuthResponse.builder()
                .token(jwtToken)
                .message("User registered successfully")
                .build();
    }

    public AuthResponse authenticate(AuthRequest request) {
        authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(
                        request.getEmail(),
                        request.getPassword()
                )
        );
        var user = userRepository.findByEmail(request.getEmail())
                .orElseThrow();
        var jwtToken = jwtUtil.generateToken(user);
        
        return AuthResponse.builder()
                .token(jwtToken)
                .message("Authentication successful")
                .build();
    }
}
