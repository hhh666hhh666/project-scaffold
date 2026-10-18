package ${PACKAGE}.common;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.stream.Collectors;

@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public Result<Void> handleBusinessException(BusinessException e) {
        log.warn("business error: {}", e.getMessage());
        return Result.fail(e.getCode(), e.getMessage());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public Result<Void> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(this::describe)
                .collect(Collectors.joining("; "));
        return Result.fail(ResultCode.BAD_REQUEST, message);
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public Result<Void> handleConstraintViolation(ConstraintViolationException e) {
        String message = e.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .collect(Collectors.joining("; "));
        return Result.fail(ResultCode.BAD_REQUEST, message);
    }

    @ExceptionHandler({
            MissingServletRequestParameterException.class,
            MethodArgumentTypeMismatchException.class
    })
    public Result<Void> handleBadArgument(Exception e) {
        return Result.fail(ResultCode.BAD_REQUEST, "请求参数不正确：" + e.getMessage());
    }

    /**
     * 请求体不是合法 JSON、或字段类型对不上（例如把字符串塞进数字字段）。
     *
     * <p>必须单独处理：它属于**调用方传错了**（400），不是服务器出了问题（500）。
     * 交给下面的兜底分支会让前端把「请求格式错」显示成「系统繁忙」，排查方向直接跑偏。
     */
    @ExceptionHandler(HttpMessageNotReadableException.class)
    public Result<Void> handleUnreadableBody(HttpMessageNotReadableException e) {
        log.warn("unreadable request body: {}", e.getMessage());
        return Result.fail(ResultCode.BAD_REQUEST, "请求体格式不正确");
    }

    @ExceptionHandler(Exception.class)
    public Result<Void> handleUnexpected(Exception e) {
        log.error("unexpected error", e);
        return Result.fail(ResultCode.SYSTEM_ERROR, ResultCode.SYSTEM_ERROR.getMessage());
    }

    private String describe(FieldError fieldError) {
        return fieldError.getField() + " " + fieldError.getDefaultMessage();
    }
}
